# Ryan Turner (turnerry@iro.umontreal.ca)
import cPickle as pkl
import ConfigParser
import os
from os.path import join, getsize
import numpy as np
import pandas as pd

# ============================================================================
# TODO move everything here to general util file


def abspath2(fname):
    return os.path.abspath(os.path.expanduser(fname))


def is_safe_name(name_str, sep_chars='_-.'):
    safe = name_str.translate(None, sep_chars).isalnum()
    return safe


def build_output_name(mc_chain_name, model_name, pkl_ext, sep='_'):
    output_name = ''.join((mc_chain_name, sep, model_name, pkl_ext))
    assert(is_safe_name(output_name))
    return output_name


def load_np(input_path, fname, ext):
    fname = os.path.join(input_path, fname + ext)
    print 'loading %s' % fname
    assert(os.path.isabs(fname))
    X = np.genfromtxt(fname, dtype=float, delimiter=',', skip_header=0,
                      loose=False, invalid_raise=True)
    return X


def load_df(input_path, fname, ext):
    """Read chain as Pandas DataFrame"""
    fname = os.path.join(input_path, fname + ext)
    print 'loading %s' % fname
    assert(os.path.isabs(fname))
    X = pd.DataFrame.from_csv(fname)
    return X


def load_fisher_info(input_path, chain_name):
    """Get fisher information from diagnostic dictionary"""
    diagnostic = load_chain_diagnostic_info(input_path, chain_name)
    if diagnostic is not None and 'max_scale' in diagnostic:
        return diagnostic['max_scale']


def load_chain_diagnostic_info(input_path, chain_name):
    """Load the diagnostic info of a specific chain"""
    for chain_diagnostic in load_input_diagnostics_gen(input_path):
        if chain_diagnostic['name'] == chain_name:
            return chain_diagnostic


def load_input_diagnostics_list(input_path):
    return list(load_input_diagnostics_gen(input_path))


def load_input_diagnostics_gen(input_path):
    """
    Returns a generator that reads the diagnostics of one sampled posterior at
    a time. They are written with successive calls to pickle.dump as the chains
    finish and their diagnostics are computed.
    """
    # TODO get this filename into a config
    fname = os.path.join(input_path, 'diagnostics.pkl')
    print 'loading %s' % fname
    with open(fname, 'rb') as f:
        while True:
            try:
                yield pkl.load(f)
            except EOFError:
                break


def chomp(ss, ext):
    L = len(ext)
    if ss[-L:] != ext:
        raise Exception('string %s with extension %s when %s was expected' %
                        (ss, ss[-L:], ext))
    return ss[:-L]

# ============================================================================


def get_chains(input_path, ext, limit=np.inf):
    chains = sorted(chomp(fname, ext) for fname in os.listdir(input_path)
        if fname.endswith(ext) and getsize(join(input_path, fname)) <= limit)
    return chains


def load_config(config_file):
    config = ConfigParser.RawConfigParser()
    assert(os.path.isabs(config_file))
    config.read(config_file)

    D = {}
    D['input_path'] = abspath2(config.get('phase1', 'output_path'))
    D['output_path'] = abspath2(config.get('phase2', 'output_path'))

    D['size_limit_bytes'] = config.getint('phase2', 'size_limit_bytes')

    D['csv_ext'] = config.get('common', 'csv_ext')
    D['pkl_ext'] = config.get('common', 'pkl_ext')
    
    njobs = config.get('compute', 'njobs')
    calc_njobs = njobs in ['', 'None', 'none', 'calculated', 'calculate']
    if calc_njobs:
        num_cores_per_cpu = config.getint('compute', 'num_cores_per_cpu')
        num_cpus = config.getint('compute', 'num_cpus')
        num_cores_per_job = config.getint('compute', 'num_cores_per_job')
        D['njobs'] = num_cores_per_cpu * num_cpus / num_cores_per_job
    else:
        try:
            D['njobs'] = int(njobs)
        except ValueError:
            raise ValueError('invalid value given for njobs: %s' % njobs)

    D['train_frac'] = config.getfloat('phase2', 'train_frac')
    assert(0.0 <= D['train_frac'] and D['train_frac'] <= 1.0)

    D['rnade_scratch'] = abspath2(config.get('phase2', 'rnade_scratch_dir'))

    D['drop_redundant_cols'] = config.getboolean('phase2', 'drop_redundant_cols')
    D['max_scale_epsilon'] = config.getfloat('phase2', 'max_scale_epsilon')
    
    return D