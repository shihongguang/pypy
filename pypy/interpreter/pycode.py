"""
PyCode class implementation.

This class is similar to the built-in code objects.
It avoids wrapping existing code object, instead,
it plays its role without exposing real code objects.
SInce in C Python the only way to crate a code object
by somehow call into the builtin compile, we implement
the creation of our code object by defining out own compile,
wich ()at the moment) calls back into the real compile,
hijacks the code object and creates our code object from that.
compile is found in the builtin.py file.
"""

# XXX todo:
# look at this if it makes sense
# think of a proper base class???

import baseobjspace, pyframe
import appfile

appfile = appfile.AppFile(__name__, ["interpreter"])

CO_VARARGS     = 0x0004
CO_VARKEYWORDS = 0x0008


class PyBaseCode(object):
    def __init__(self):
        self.co_name = ""
        self.co_flags = 0
        self.co_varnames = ()
        self.co_argcount = 0
        self.co_freevars = ()
        self.co_cellvars = ()
        
    def build_arguments(self, space, w_arguments, w_kwargs, w_defaults, w_closure):
        # We cannot systematically go to the application-level (_app.py)
        # to do this dirty work, for bootstrapping reasons.  So we check
        # if we are in the most simple case and if so do not go to the
        # application-level at all.
        co = self
        if (co.co_flags & (CO_VARARGS|CO_VARKEYWORDS) == 0 and
            (w_kwargs   is None or not space.is_true(w_kwargs))   and
            (w_closure  is None or not space.is_true(w_closure))):
            # looks like a simple case, see if we got exactly the correct
            # number of arguments
            try:
                args = space.unpacktuple(w_arguments, self.co_argcount)
            except ValueError:
                pass  # no
            else:
                # yes! fine!
                argnames = [space.wrap(name) for name in co.co_varnames]
                w_arguments = space.newdict(zip(argnames, args))
                return w_arguments
        # non-trivial case.  I won't do it myself.
        if w_kwargs   is None: w_kwargs   = space.newdict([])
        if w_defaults is None: w_defaults = space.newtuple([])
        if w_closure  is None: w_closure  = space.newtuple([])
        w_bytecode = space.wrap(co)
        w_arguments = space.gethelper(appfile).call(
            "decode_code_arguments", [w_arguments, w_kwargs, w_defaults,
                                      w_bytecode])
        # we assume that decode_code_arguments() gives us a dictionary
        # of the correct length.
        if space.is_true(w_closure):
            l = zip(co.co_freevars, space.unpackiterable(w_closure))
            for key,cell in l:
                w_arguments._appendcell(space, space.wrap(key), cell)
        return w_arguments
        
class PyByteCode(PyBaseCode):
    """Represents a code object for Python functions.

    Public fields:
    to be done
    """

    def __init__(self):
        """ initialize all attributes to just something. """
        PyBaseCode.__init__(self)
        self.co_filename = ""
        self.co_code = None
        self.co_consts = ()
        self.co_names = ()
        self.co_nlocals = 0
        self.co_stacksize = 0
        # The rest doesn't count for hash/cmp
        self.co_firstlineno = 0 #first source line number
        self.co_lnotab = "" # string (encoding addr<->lineno mapping)
        
    ### codeobject initialization ###

    def _from_code(self, code):
        """ Initialize the code object from a real one.
            This is just a hack, until we have our own compile.
            At the moment, we just fake this.
            This method is called by our compile builtin function.
        """
        import types
        assert type(code) is types.CodeType
        # simply try to suck in all attributes we know of
        for name in self.__dict__.keys():
            value = getattr(code, name)
            setattr(self, name, value)
        newconsts = ()
        for const in code.co_consts:
            if isinstance(const, types.CodeType):
                newc = PyByteCode()
                newc._from_code(const)
                newconsts = newconsts + (newc,)
            else:
                newconsts = newconsts + (const,)
        self.co_consts = newconsts

    def eval_code(self, space, w_globals, w_locals):
        frame = pyframe.PyFrame(space, self, w_globals, w_locals)
        ec = space.getexecutioncontext()
        w_ret = ec.eval_frame(frame)
        return w_ret
