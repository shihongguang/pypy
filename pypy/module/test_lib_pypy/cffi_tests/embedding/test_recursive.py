# Generated by pypy/tool/import_cffi.py
from pypy.module.test_lib_pypy.cffi_tests.embedding.test_basic import EmbeddingTests


class TestRecursive(EmbeddingTests):
    def test_recursive(self):
        add_recursive_cffi = self.prepare_module('add_recursive')
        self.compile('add_recursive-test', [add_recursive_cffi])
        output = self.execute('add_recursive-test')
        assert output == ("preparing REC\n"
                          "some_callback(400)\n"
                          "adding 400 and 9\n"
                          "<<< 409 >>>\n"
                          "adding 40 and 2\n"
                          "adding 100 and -5\n"
                          "got: 42 95\n")
