class CheckAllocation:
    def teardown_method(self, fun):
        from rpython.rtyper.lltypesystem import ll2ctypes
        import gc
        tries = 20
        # remove the GC strings from ll2ctypes
        for key, value in ll2ctypes.ALLOCATED.items():
            if value._TYPE._gckind == 'gc':
                del ll2ctypes.ALLOCATED[key]
        #
        while tries and ll2ctypes.ALLOCATED:
            gc.collect() # to make sure we disallocate buffers
            tries -= 1
        assert not ll2ctypes.ALLOCATED
