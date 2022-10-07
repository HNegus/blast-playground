import unittest
import os
import testUtils

@testUtils.lint_jupyter_notebook('file.ipynb')
class TestStudentCode(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()