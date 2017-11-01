import json
import numpy
import os
import pathlib
import pickle
import tempfile

def write_delimited(path, data, delimiter='\t'):
    """Write a list of lists to a delimited file."""
    path = pathlib.Path(path)
    try:
        with path.open('w') as f:
            f.write('\n'.join(','.join(map(str, row)) for row in data))
    except:
        if path.exists():
            path.remove()

def read_delimited(path, header=True, coerce_float=True, empty_val=numpy.nan, delimiter='\t'):
    """Iterate over the rows in a delimited file such as a csv or tsv.

    Iterate a delimited file line by line, yielding each line's contents split
    by the delimiter and optionally converted to floating-point values if possible.

    Note: empty lines are skipped.

    If more sophisticated control is required, consider numpy.genfromtext or
    numpy.loadtxt.

    Parameters:
        path: path to input file
        header: if True (default), return the header line and an iterator over
            the remaining lines. If False, return an iterator over all lines.
        coerce_float: if True (default), attempt to convert data values to
            floating point. If that fails, return the original input string.
        empty_val: if coerce_float is True, return this value when an input
            value is empty. '' or numpy.nan (default) are the usual choices.
        delimiter: symbol on which the file is delimited.

    Returns:
        (header, iterator) if coerce_float is True, else iterator
        where header is a list of the strings on the first line, and iterator
        yields a list of values for each subsequent line.

    Example:
        header, data = read_delimited('path/to/data.csv', delimiter=',')
        name_i = header.index('name')
        lifespan_i = header.index('lifespan')
        lifespans = {}
        for row in data:
            lifespans[row[name_i]] = row[lifespan_i]
    """
    data_iter = _iter_delimited(path, header, coerce_float, empty_val, delimiter)
    if header:
        return next(data_iter), data_iter
    else:
        return data_iter

def _iter_delimited(path, header, coerce_float, empty_val, delimiter):
    with open(path) as infile:
        for line in infile:
            vals = line.strip('\n').split(delimiter)
            if not vals:
                continue # skip blank lines
            if header:
                header = False # only read first (non-empty) line as the header
                yield vals
            elif not coerce_float:
                yield vals # don't try to convert to float, just return strings
            else:
                new_vals = []
                for val in vals:
                    if val == '':
                        val = empty_val
                    else:
                        try:
                            val = float(val)
                        except ValueError:
                            pass
                    new_vals.append(val)
                yield new_vals

def dump(path, **data_dict):
    """Dump the keyword arguments into a dictionary in a pickle file."""
    path = pathlib.Path(path)
    try:
        with path.open('wb') as f:
            pickle.dump(data_dict, f)
    except:
        if path.exists():
            path.remove()

def load(path):
    """Load a dictionary from a pickle file into a Data object for
    attribute-style value lookup. The path to the original file
    from which the data was loaded is stored in the '_path' attribute."""
    path = pathlib.Path(path)
    with path.open('rb') as f:
        return Data(_path=path, **pickle.load(f))

class Data:
    def __init__(self, **kwargs):
        """Add all keyword arguments to self.__dict__, which is to say, to
        the namespace of the class. I.e.:

        d = Data(foo=5, bar=6)
        d.foo == 5 # True
        d.bar > d.foo # True
        d.baz # AttributeError
        """
        self.__dict__.update(kwargs)

class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that is smart about converting iterators and numpy arrays to
    lists, and converting numpy scalars to python scalars.
    """
    def default(self, o):
        try:
            return super().default(o)
        except TypeError:
            if isinstance(o, numpy.generic):
                item = o.item()
                if isinstance(item, numpy.generic):
                    raise
                else:
                    return item
            try:
                return list(o)
            except:
                raise

_COMPACT_ENCODER = _NumpyEncoder(separators=(',', ':'))
_READABLE_ENCODER = _NumpyEncoder(indent=4, sort_keys=True)

def json_encode_compact_to_bytes(data):
    """Encode compact JSON for transfer over the network or similar."""
    return _COMPACT_ENCODER.encode(data).encode('utf8')

def json_encode_legible_to_str(data):
    """Encode nicely-formatted JSON to a string."""
    return _READABLE_ENCODER.encode(data)

def json_encode_legible_to_file(data, f):
    """Encode nicely-formatted JSON to an open file handle."""
    for chunk in _READABLE_ENCODER.iterencode(data):
        f.write(chunk)

def json_encode_atomic_legible_to_file(data, filename):
    """Encode nicely-formatted JSON and if there was no error, atomically write.

    Care is taken to never overwrite an existing file except in an atomic manner
    after all other steps have occured. This prevents errors from causing a
    partial overwrite of an existing file: the result of this function is all or
    none.

    Parameters:
        data: python objects to be JSON encoded
        filename: string or pathlib.Path object for destination file.
    """
    s = json_encode_legible_to_str(data)
    filename = pathlib.Path(filename)
    prefix = filename.name + '-temp.'
    fd, tmp_path = tempfile.mkstemp(prefix=prefix, dir=str(filename.parent))
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(s)
        os.replace(str(tmp_path), str(filename))
    except:
        os.remove(tmp_path)
        raise