#!/usr/bin/env python

from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
import json
from chris_plugin import chris_plugin, PathMapper
import subprocess

__version__ = '1.0.0'

DISPLAY_TITLE = r"""
       _        _ _     _       _               
      | |      | | |   | |     | |              
 _ __ | |______| | | __| |  ___| |__ __  ___ __ 
| '_ \| |______| | |/ _` | / __| '_ \\ \/ / '__|
| |_) | |      | | | (_| || (__| | | |>  <| |   
| .__/|_|      |_|_|\__,_| \___|_| |_/_/\_\_|   
| |                    ______                   
|_|                   |______|                  
"""


parser = ArgumentParser(description='A ChRIS plugin to analyze the result produced by an LLD analysis ',
                        formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument('-f', '--fileFilter', default='json', type=str,
                    help='input file filter glob')
parser.add_argument('-e', '--marginOfError', default=0.02, type=float,
                    help='Accepted margin of error in tibia to femur ratio')
parser.add_argument('-V', '--version', action='version',
                    version=f'%(prog)s {__version__}')


# The main function of this *ChRIS* plugin is denoted by this ``@chris_plugin`` "decorator."
# Some metadata about the plugin is specified here. There is more metadata specified in setup.py.
#
# documentation: https://fnndsc.github.io/chris_plugin/chris_plugin.html#chris_plugin
@chris_plugin(
    parser=parser,
    title='A ChRIS plugin to analyze the result produced by an LLD analysis',
    category='',                 # ref. https://chrisstore.co/plugins
    min_memory_limit='100Mi',    # supported units: Mi, Gi
    min_cpu_limit='1000m',       # millicores, e.g. "1000m" = 1 CPU core
    min_gpu_limit=0              # set min_gpu_limit=1 to enable GPU
)
def main(options: Namespace, inputdir: Path, outputdir: Path):
    """
    *ChRIS* plugins usually have two positional arguments: an **input directory** containing
    input files and an **output directory** where to write output files. Command-line arguments
    are passed to this main method implicitly when ``main()`` is called below without parameters.

    :param options: non-positional arguments parsed by the parser given to @chris_plugin
    :param inputdir: directory containing (read-only) input files
    :param outputdir: directory where to write output files
    """

    print(DISPLAY_TITLE)

    # Typically it's easier to think of programs as operating on individual files
    # rather than directories. The helper functions provided by a ``PathMapper``
    # object make it easy to discover input files and write to output files inside
    # the given paths.
    #
    # Refer to the documentation for more options, examples, and advanced uses e.g.
    # adding a progress bar and parallelism.
    mapper = PathMapper.file_mapper(inputdir, outputdir, glob=f"**/*.{options.fileFilter}",fail_if_empty=False)
    for input_file, output_file in mapper:
        with open(input_file) as f:
            data = json.load(f)
            analyze_measurements(data,options.marginOfError)


def analyze_measurements(data, margin_error):
    """
    Analyze the measurements of lower limbs and verify
    if the measurements are correct.
    """
    AVG_RATIO = 0.8
    for row in data:
        rt = data[row]["pixel_distance"]["Right tibia"]
        rf = data[row]["pixel_distance"]["Right femur"]
        ratio = round(rt / rf, 2)
        print(f"Calculated tibia to femur ratio: {ratio} [Average ratio: {AVG_RATIO} ± {margin_error}]")
        if ratio > AVG_RATIO + margin_error or ratio < AVG_RATIO - margin_error:
            print("Measurements are incorrect.")
        else:
            print("Measurements are correct.")



if __name__ == '__main__':
    main()
