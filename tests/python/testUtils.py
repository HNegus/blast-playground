import os
import re
import json
import unittest
import subprocess
from typing import (
    Any, Dict, Generator, List, Optional, Tuple, Union,
)

os.environ['SOURCE_DIR'] = "./"

def run_formatter():
    os.system('black -l 500 ' + os.getenv("SOURCE_DIR"))

def run_student_file(file_name: str, arguments: Optional[List[str]] = [],
                     seed: Optional[Union[int, None]] = None,
                     open_files: Optional[bool] = False) -> str:
    """
        Run a file in a subprocess.
        The function returns a string representation of
        the stdout values from the subprocess.
    """
    cmd = 'python3 '

    if seed is not None or open_files:
        cmd += f"-c \"fopen=open;"
        # Execute the file with a set `random` seed
        if seed is not None:
            cmd += f"import random;random.seed({seed});"
        # Make sure the function `open` refers to SOURCE_DIR
        if open_files:
            cmd += f"open=(lambda fname, *args, **kwargs: fopen('{os.getenv('SOURCE_DIR')}'+fname, *args, **kwargs));"
        cmd += f"exec(fopen('{os.getenv('SOURCE_DIR')}{file_name}').read())\""
    else:
        cmd += f"{os.getenv('SOURCE_DIR')}{file_name}"

    # Start the process
    proc = subprocess.Popen(cmd,
                            shell=True, stdout=subprocess.PIPE,
                            stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    for argument in arguments:
        proc.stdin.write(argument.encode('utf8') + b"\n")
        proc.stdin.flush()

    proc.stdin.close()
    proc.wait()

    stderr = proc.stderr.read()
    proc.stderr.close()
    stdout = proc.stdout.read()
    proc.stdout.close()
    # Give output - either an error or the terminal stdout
    if len(stderr) > 0:
        raise RuntimeError(
            "Program encountered an error during runtime exit code [" + str(proc.returncode) + "] stdout [" + str(stdout) + "] stderr [" + str(stderr) + "]"
        )
    return str(stdout).lower()

def lint_jupyter_notebook(file_name):
    """
        Build a specific decorator oriented around
        a particular Jupyter Notebook.
    """

    def add_tests(test_object):
        """
            Decorator that adds functions to the unittest TestCase
            to format and test a provided Jupyter Notebook.
        """

        get_source = lambda cell: (cell['source']
                                   if cell['source'].__class__.__name__ == 'str'
                                   else "".join(cell['source'])
                                   )

        # @message: Deze test controleert of je Jupyter Notebook correct
        # is geformatteerd.
        # Jupyter zou dit standaard moeten regelen, dus controleer of je
        # het goede bestand hebt ingeleverd!
        def correct_formaat(self):
            notebook = load_notebook()

            self.assertIn('metadata', notebook)
            self.assertIn('nbformat', notebook)
            self.assertIn('nbformat_minor', notebook)
            self.assertIn('cells', notebook)

            self.assertGreater(len(notebook['cells']), 0)
            # We require nbformat 4 or higher.
            # This was already the latest stable version when
            # the Bit Academy has started offering exercises
            # that involve Jupyter Notebooks, so no need
            # to write older Jupyter Notebooks than that.
            self.assertGreaterEqual(notebook['nbformat'], 4)

        # @message: Deze test controleert of je Jupyter Notebook begint met
        # een titel in Markdown aan het begin van je bestand.
        def begint_met_titel(self):
            notebook = load_notebook()

            cell = notebook['cells'][0]

            try:
                self.assertEqual(cell['cell_type'], 'markdown')
            except AssertionError as e:
                e.args = ("Your Jupyter Notebook doesn't start with a markdown block.",)
                raise e

            desc = get_source(cell)
            try:
                self.assertRegex(desc, r"^\n* *# \S")
            except AssertionError as e:
                e.args = ("The Jupyter Notebook doesn't start with a title. Make sure you put a h1-header at the top.",)
                raise e

        # @message: Elk netjes Jupyter Notebook begint met een titel
        # en een beschrijving in Markdown.
        # Deze test controleert of je Jupyter begint met een titel
        # en een beschrijving aan het begin van je bestand.
        def heeft_beschrijving(self):
            def evaluate_markdown_blocks(md_cells):
                text = "\n\n".join(md_cells)
                for header, description in re.findall(r"(#+ [\S ]+)\s*([^#\n]*\n?)", text):
                    if description == "":
                        e = f"Header `{header}` has no description."
                        raise AssertionError(e)
                    if re.findall(r"[.:,;!?]", description) == []:
                        e = f"Header `{header}` is supposed to have at least one sentence as a description. Instead its description is `{description[:10] + '...' if len(description) > 10 else description}`. Make sure your sentence is spelled correctly and uses punctuation."
                        raise AssertionError(e)

            # In case the title is in a different Markdown cell than
            # the description, (which  some people do) gather all
            # adjacent Markdown cells and look at them together.
            notebook = load_notebook()
            markdown_cells = []

            for cell in notebook['cells']:
                if cell['cell_type'] != 'markdown':
                    evaluate_markdown_blocks(markdown_cells)
                    markdown_cells = []
                else:
                    markdown_cells.append(get_source(cell))
            else:
                evaluate_markdown_blocks(markdown_cells)

        # @message: Hier wordt gecontroleerd of de headers een goede
        # structuur hebben, waar een subheader altijd een niveau dieper
        # is dan de bovenliggende header.
        def opgedeeld_in_headers(self):
            notebook = load_notebook()

            markdown_cells = "\n\n".join([
                get_source(cell) for cell in notebook['cells']
                if cell['cell_type'] == 'markdown'
            ])

            headers = re.findall(r"\s?(#+) ([\S ]+)", markdown_cells)

            current = ""
            for h, title in headers:
                if len(h) > len(current):
                    self.assertEqual(h + ' ' + title, current + '# ' + title)
                elif len(h) == 1:
                    e = "Cannot use two document titles (h1-headers) in one Jupyter Notebook."
                    raise AssertionError(e)
                else:
                    # A header that is bigger than an h1-header
                    # but is between h2 and then current header,
                    # is always permitted.
                    pass

                current = h

        # @message: Hier wordt gecontroleerd dat er nooit twee blokken code
        # achter elkaar staan in je Jupyter Notebook.
        # Deze test negeert lege blokken code aan het einde van je Jupyter
        # Notebook, dus controleer dat je niet ergens halverwege je bestand
        # over het hoofd hebt gezien.
        def geen_blokken_naast_elkaar(self):
            notebook = load_notebook()

            block_types = [
                cell['cell_type'] for cell in notebook['cells']
            ]

            # Ignore empty code blocks at the end
            while get_source(notebook['cells'][len(block_types) - 1]) == '':
                block_types = block_types[:-1]

            for i in range(len(block_types) - 1):
                # Check if two adjacent blocks are code blocks
                if block_types[i] == 'code' == block_types[i + 1]:
                    first_line = get_source(notebook['cells'][i]).split('\n')[0]
                    if len(first_line) > 20:
                        first_line = first_line[:17] + '...'

                    second_line = get_source(notebook['cells'][i + 1]).split('\n')[0]
                    if len(second_line) > 20:
                        second_line = second_line[:17] + '...'

                    e = f"Two code blocks found next to each other. The first one starts with `{first_line}` and the second one starts with `{second_line}`."
                    raise AssertionError(e)

        def imports_op_juiste_plek(self):
            notebook = load_notebook()
            notebook, modules = open_notebook(notebook)
            browse_for_used_imports(notebook, modules)

            notebook = nest_document(notebook)

            for module in modules:
                correct_import = determine_longest_path(notebook, module)
                if correct_import is None:
                    e = f"Module `{module}` is imported but isn't being used anywhere."
                    raise AssertionError(e)
                if module not in correct_import[-1]['has_imports']:
                    e = f"Expected module `{module}` to be imported at header `{correct_import[-1]['title']}`."
                    raise AssertionError(e)

        # Register jupyter notebook tests
        func_name = "".join([word.capitalize() for word in file_name.split('.')])
        set_test = lambda func, name: setattr(test_object, name, func)

        set_test(correct_formaat, f'test_jupyterNotebook{func_name}HeeftCorrectFormaat')
        set_test(begint_met_titel, f'test_jupyterNotebook{func_name}BegintMetEenTitel')
        set_test(heeft_beschrijving, f'test_jupyterNotebook{func_name}HeeftEenBeschrijving')
        set_test(opgedeeld_in_headers, f'test_jupyterNotebook{func_name}IsOpgedeeldInStukkenMetHeaders')
        set_test(geen_blokken_naast_elkaar, f'test_jupyterNotebook{func_name}HeeftNooitTweeCodeBlokkenNaastElkaar')
        set_test(imports_op_juiste_plek,
                 f'test_jupyterNotebook{func_name}ImporteertModulesEnVariabelenInHetJuisteCodeblok')

        return test_object

    def load_notebook(file_name: Optional[str] = file_name,
                      nested_format: Optional[bool] = False) -> Dict[str, Any]:
        """
            Load a Jupyter Notebook as if it were a JSON formatted file.
            If `nested_format` is True, the Jupyter Notebook is formatted
            in a way where
        """
        with open(os.getenv('SOURCE_DIR') + file_name, 'r', encoding='utf-8') as open_file:
            n = json.load(open_file)

        return n if not nested_format else n  # TODO: Format Notebook nicely

    def find_imported_modules(code: str) -> Generator[str, None, None]:
        """
            Detect any modules that are imported in the code.
            The generator iterates over the found modules.
        """
        discovered = re.findall(
            r"(?:from [\w.\-]+)?\s*import (?:((?:(?: *[\w.\-]+(?: as [\w.\-]+)?),? *)+)|(?:\(\s*)((?:(?: *[\w.\-]+(?: as [\w.\-]+)?),?\s*)+)(?:\s*\))|(?:\*))",
            code
        )

        for line in discovered:
            for option in line:
                for mod in re.findall(
                        r"(?:(?:(?:[\w.\-]+ as ([\w.\-]+))|([\w.\-]+)),)*(?:(?:[\w.\-]+ as ([\w.\-]+))|([\w.\-]+))",
                        option):
                    for result in mod:
                        if len(result) > 0 and result != "*":
                            yield result

    def is_code_block(code : str) -> bool:
        """
            Determine whether a code block is considered a "code" block.
        """
        return re.fullmatch(
            r"(?:(?:(?:from [\w.\-]+)?\s*import (?:(?:(?:(?: *[\w.\-]+(?: as [\w.\-]+)?),? *)+)|(?:\(\s*)(?:(?:(?: *[\w.\-]+(?: as [\w.\-]+)?),?\s*)+)(?:\s*\))|(?:\*))|(?:#[^\n]+)|(?:\"\"\"(?:.+)\"\"\")|(?:[A-Z][A-Z_\-]*\s*=\s*(?:\d+|(?:\"[^\"]+\")|(?:\'[^\']+\')|(?:\"\"\"[^(?:\"\"\")]+\"\"\"))))\s*)+",
            code.strip()
        )

    def look_for_necessary(current_modules : List[Any], looking_for_mod : str) -> Generator[Dict[str, Union[int, str, List[Any]]], None, None]:
        """
            Look for modules that use a certain module.
            Yield all paths towards blocks using the module.
        """
        cursor = current_modules[-1]

        if looking_for_mod in cursor['uses_imports']:
            yield current_modules
        else:
            for child in cursor['children']:
                yield from look_for_necessary(
                    current_modules + [child],
                    looking_for_mod)

    def determine_longest_path(document, given_module):
        """
            Determine the longest path that can be made
            while still covering all relevant nodes.
        """
        longest_path: Union[List[Dict], None] = None

        for path in look_for_necessary(document, given_module):
            if longest_path is None:
                longest_path = path
            else:
                # Evaluate the longest subpath that is still the same
                for i in range(len(longest_path)):
                    if longest_path[i] != path[i]:
                        longest_path = longest_path[:i]
                        break

        return longest_path

    def open_notebook(notebook) -> Tuple[List[Dict[str, Union[str, int, List[Any]]]], List[str]]:
        """
            Open the Jupyter Notebook and extract
            the relevant blocks in a useful format.

            The function returns the format and
            a list of imported modules it has found.
        """
        cells = notebook['cells']
        cells = [
            {
                'type'  : cell['cell_type'],
                'source': (cell['source'] if cell['source'].__class__.__name__ == 'str' else "".join(cell['source'])),
            }
            for cell in cells if cell['cell_type'] in ['markdown', 'code']
        ]

        # Group all code with their respective headers
        header_and_code_only_cells = []
        found_imports = []
        seen_markdown_blok = False

        for cell in cells:
            if cell['type'] == 'markdown':
                seen_markdown_blok = True
                for stars, title in re.findall(r"\n\s*(#+) +([^\n]+)\n*", '\n' + cell['source']):

                    # Build header in favourable format
                    header_and_code_only_cells.append({
                        'title': stars + ' ' + title,
                        'header': len(stars),
                        'code': [],
                        'children': [],
                        'uses_imports': [], # Which modules it needs in its code blocks
                        'has_imports': [],  # Which modules it has imported in its code blocks
                    })

            else:
                if not seen_markdown_blok:
                    e = "Discovered a code block before any Markdown block. You probably forgot to add a title to the Jupyter Notebook, or you placed the code block in front of it."
                    raise AssertionError(e)

                # Build code and evaluate imports
                header_and_code_only_cells[-1]['code'].append(cell['source'])

                for module in find_imported_modules(cell['source']):
                    if module in found_imports:
                        raise AssertionError(
                            f"Found variable `{module}` imported multiple times: second import found at header `{header_and_code_only_cells[-1]['title']}`"
                        )

                    found_imports.append(module)
                    header_and_code_only_cells[-1]['has_imports'].append(module)
        return header_and_code_only_cells, found_imports

    def browse_for_used_imports(unnested_cells, modules):
        """
            Register in all blocks whether an imported module is used there.
        """
        # Look at which modules are used where
        for header in unnested_cells:
            for code in header['code']:
                if not is_code_block(code):
                    for module in modules:
                        if module in code:
                            header['uses_imports'].append(module)

    def nest_document(unnested_cells):
        """
            Nest the Jupyter Notebook cells into each other.
        """
        # Nest sub-headers as children from headers
        unnested_cells.reverse()
        document = []

        for header in unnested_cells:
            if document == []:
                document.append(header)
            else:
                for subheader in document:
                    if header['header'] < subheader['header']:
                        header['children'].append(subheader)

                for child in header['children']:
                    document.remove(child)

                document = [header] + document
        return document

    return add_tests
