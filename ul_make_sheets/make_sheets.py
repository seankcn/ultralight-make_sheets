#!/usr/bin/env python

"""Program to take character definitions and build a PDF of the
character sheet."""

import argparse
import logging
import os
from itertools import product
from multiprocessing import Pool, cpu_count
from pathlib import Path
from pypdf import PdfWriter
from typing import Union, Sequence, Optional, List

from ul_make_sheets import (
    character as _char,
    exceptions,
    readers,
    latex,
    monsters,
    forms,
)
from ul_make_sheets.character import Character
from ul_make_sheets.fill_pdf_template import (
    create_character_pdf_template,
    create_personality_pdf_template,
    create_spells_pdf_template,
)
from ul_make_sheets.pdf_image_insert import insert_image_into_pdf

log = logging.getLogger(__name__)

ORDINALS = {
    1: "1st",
    2: "2nd",
    3: "3rd",
    4: "4th",
    5: "5th",
    6: "6th",
    7: "7th",
    8: "8th",
    9: "9th",
}

jinja_env = forms.jinja_environment()
jinja_env.filters["rst_to_latex"] = latex.rst_to_latex
jinja_env.filters["boxed"] = latex.rst_to_boxlatex
jinja_env.filters["spellsheetparser"] = latex.msavage_spell_info
jinja_env.filters["monsterdoc"] = latex.RPGtex_monster_info

# Custom types
File = Union[Path, str]


class CharacterRenderer:
    def __init__(self, template_name: str):
        self.template_name = template_name

    def __call__(
        self,
        character: Character,
        content_suffix: str = "tex",
        use_dnd_decorations: bool = False,
        spell_order: bool = False
    ):
        template = jinja_env.get_template(
            self.template_name.format(suffix=content_suffix)
        )
        return template.render(
            character=character,
            use_dnd_decorations=use_dnd_decorations,
            spell_order=spell_order,
            ordinals=ORDINALS,
        )


create_character_sheet_content = CharacterRenderer("character_sheet_template.{suffix}")
create_subclasses_content = CharacterRenderer("subclasses_template.{suffix}")
create_features_content = CharacterRenderer("features_template.{suffix}")
create_magic_items_content = CharacterRenderer("magic_items_template.{suffix}")
create_spellbook_content = CharacterRenderer("spellbook_template.{suffix}")
create_infusions_content = CharacterRenderer("infusions_template.{suffix}")
create_druid_shapes_content = CharacterRenderer("druid_shapes_template.{suffix}")


def create_monsters_content(
    monsters: Sequence[Union[monsters.Monster, str]],
    suffix: str,
    base_template: str = "monsters_template",
) -> str:
    # Convert strings to Monster objects
    template = jinja_env.get_template(base_template + f".{suffix}")
    spell_list = [Spell() for monster in monsters for Spell in monster.spells]
    return template.render(
        monsters=monsters,
        spell_list=spell_list,
    )

def make_sheet(
    sheet_file: File,
    debug: bool = False,
    spell_order: bool = False,
):
    """Make a character or GM sheet into a PDF.
    Parameters
    ----------
    sheet_file
      File (.py) to load character from. Will save PDF using same name
    debug : bool, optional
      Provide extra info and preserve temporary files.

    """
    # Parse the file
    sheet_file = Path(sheet_file)
    # Create the sheet
    ret = make_character_sheet(
        char_file=sheet_file,
        debug=debug,
        spell_order=spell_order,
    )
    return ret

def make_character_content(
    character: Character,
    spell_order: bool = False,
) -> List[str]:
    """Prepare the inner content for a character sheet.

    This will produce a fully renderable document, suitable for
    passing to routines in either the ``epub`` or ``latex``
    modules. If *content_format* is ``"html"``, the returned content
    is just the portion that would be found inside the
    ``<body></body>`` tag.

    If *content_format* is ``"tex"``, the content returned will not
    include the character, spell list, or biography sheets, since
    these are currently processed through fillable PDFs.

    Parameters
    ----------
    character
      The character to render content for.
    content_format
      Which markup syntax to use, "tex" or "html".

    Returns
    -------
    content
      The list of rendered character sheet contents for *character* in
      markup format *content_format*.

    """
    # Preamble, empty for HTML
    content_format = "tex"
    content = [
        jinja_env.get_template(f"preamble.{content_format}").render(
            title="Features, Magical Items and Spells",
        )
    ]
    # Create a list of subcasses, features, spells, etc
    if len(getattr(character, "subclasses", [])) > 0:
        content.append(
            create_subclasses_content(
                character,
                content_suffix=content_format,
            )
        )
    if len(getattr(character, "features", [])) > 0:
        content.append(
            create_features_content(
                character,
                content_suffix=content_format,
            )
        )
    if character.magic_items:
        content.append(
            create_magic_items_content(
                character,
                content_suffix=content_format,
            )
        )
    if len(getattr(character, "spells", [])) > 0:
        content.append(
            create_spellbook_content(
                character,
                content_suffix=content_format,
                spell_order=spell_order,
            )
        )
    if len(getattr(character, "infusions", [])) > 0:
        content.append(
            create_infusions_content(
                character,
                content_suffix=content_format,
            )
        )

    # Create a list of Druid wild_shapes
    if len(getattr(character, "all_wild_shapes", [])) > 0:
        content.append(
            create_druid_shapes_content(
                character,
                content_suffix=content_format,
            )
        )

    # Create a list of companions
    if len(getattr(character, "companions", [])) > 0:
        content.append(
            create_monsters_content(
                character.companions,
                suffix=content_format,
                base_template="companions_template",
            )
        )
    # Postamble, empty for HTML
    content.append(
        jinja_env.get_template(f"postamble.{content_format}").render()
    )
    return content



def make_character_sheet(
    char_file: Union[str, Path],
    character: Optional[Character] = None,
    debug: bool = False,
    spell_order: bool = False,
):
    """Prepare a PDF character sheet from the given character file.

    Parameters
    ----------
    basename
      The basename for saving files (PDFs, etc).
    character
      If provided, will not load from the character file, just use
      file for PDF name
    debug
      Provide extra info and preserve temporary files.

    """
    # Load properties from file
    if character is None:
        character_props = readers.read_sheet_file(char_file)
        character = _char.Character.load(character_props)
    # Set the fields in the FDF
    basename = char_file.stem
    char_base = basename + "_char"
    person_base = basename + "_person"
    sheets = [char_base + ".pdf"]
    pages = []
    # Prepare the tex/html content
    # Create a list of features and magic items
    content = make_character_content(
        character=character,
        spell_order=spell_order,
    )
    # Fillable PDF forms
    sheets.append(person_base + ".pdf")
    char_pdf = create_character_pdf_template(
        character=character, basename=char_base
    )
    pages.append(char_pdf)
    person_pdf = create_personality_pdf_template(
        character=character, basename=person_base,
    )
    pages.append(person_pdf)
    if character.is_spellcaster:
        # Create spell sheet
        spell_base = "{:s}_spells".format(basename)
        created_basenames = create_spells_pdf_template(
            character=character, basename=spell_base
        )
        for spell_base in created_basenames:
            sheets.append(spell_base + ".pdf")
    # Combined with additional LaTeX pages with detailed character info
    features_base = "{:s}_features".format(basename)
    try:
        if len(content) > 2:
            latex.create_latex_pdf(
                tex="".join(content),
                basename=features_base,
                keep_temp_files=debug,
            )
            sheets.append(features_base + ".pdf")
            final_pdf = f"{basename}.pdf"
            merge_pdfs(sheets, final_pdf, clean_up=not (debug))
            for image in character.images:
                insert_image_into_pdf(final_pdf, *image)
    except exceptions.LatexNotFoundError:
        log.warning(
            f"``pdflatex`` not available. Skipping features for {character.name}"
        )


def merge_pdfs(src_filenames, dest_filename, clean_up=False):
    """Merge several PDF files into a single final file.

    src_filenames
      Iterable of source PDF file paths to use.
    dest_filename
      Path to requested PDF filename, will be overwritten if it
      exists.
    clean_up : optional
      If truthy, the ``src_filenames`` will be deleted once the
      ``dest_filename`` has been created.

    """    
    merger = PdfWriter()
    for pdf in src_filenames:
        merger.append(pdf)
    merger.set_need_appearances_writer(True)
    merger.write(dest_filename)
    merger.close()
    if clean_up:
        for sheet in src_filenames:
            os.remove(sheet)


def _build(filename, args) -> int:
    basename = filename.stem
    print(f"Processing {basename}...")
    try:
        make_sheet(
            sheet_file=filename,
            debug=args.debug,
            spell_order=args.spell_order,
        )
    except exceptions.CharacterFileFormatError:
        # Only raise the failed exception if this file is explicitly given
        print(f"invalid {basename}")
        if args.filename:
            raise
    except Exception:
        print(f"{basename} failed")
        raise
    else:
        print(f"{basename} done")
    return 1


def main(args=None):
    # Prepare an argument parser
    parser = argparse.ArgumentParser(
        description="Prepare Dungeons and Dragons character sheets as PDFs"
    )
    parser.add_argument(
        "filename",
        type=str,
        nargs="*",
        help="File with character definition, or directory containing such files",
    )
    parser.add_argument(
        "--spells-by-level",
        "-S",
        default=False,
        action="store_true",
        help="Order spells by level in the feature pages.",
        dest="spell_order",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Provide verbose logging for debugging purposes.",
    )
    args = parser.parse_args(args)
    # Prepare logging if necessary
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    # Build the true list of filenames
    input_filenames = args.filename
    known_extensions = readers.readers_by_extension.keys()
    if input_filenames == []:
        input_filenames = [Path()]
    else:
        input_filenames = [Path(f) for f in input_filenames]

    def get_char_files(fpath, parse_dirs = True):
        valid_files = []
        if fpath.is_dir() and parse_dirs == True:
            for f in fpath.iterdir():
                valid_files.extend(get_char_files(f, parse_dirs=False))
        if fpath.suffix in known_extensions:
            valid_files.append(fpath)
        else:
            log.info(f"Unhandled file: {str(fpath)}")
        return valid_files

    filenames = []
    for fpath in input_filenames:
        filenames.extend(get_char_files(fpath, True))
    # Process the requested files
    if args.debug:
        for filename in filenames:
            log.debug("building")
            _build(filename, args)
    else:
        with Pool(cpu_count()) as p:
            p.starmap(_build, product(filenames, [args]))


if __name__ == "__main__":
    main()
