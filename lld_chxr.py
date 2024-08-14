#!/usr/bin/env python

from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
import json
from chris_plugin import chris_plugin, PathMapper
import subprocess
from difflib import SequenceMatcher
import re
import sys

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
parser.add_argument('-m', '--measurementsUnit', default='', type=str,
                    help='Accepted unit for length measurements')
parser.add_argument('-d', '--limbDifference', default=sys.float_info.max, type=float,
                    help='Accepted difference in both limbs')
parser.add_argument('-s', '--splitToken', default='', type=str,
                    help='If specified, use this token to split the input tags.')
parser.add_argument('-k', '--splitKeyValue', default='', type=str,
                    help='If specified, use this char to split key value.')
parser.add_argument('-t', '--tagInfo', default='', type=str,
                    help='Specify accepted tags and their values here.')
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
    tagStruct = {}
    if options.tagInfo:
        tagStruct = tagInfo_to_tagStruct(options)

    mapper = PathMapper.file_mapper(inputdir, outputdir, glob=f"**/*.{options.fileFilter}",fail_if_empty=False)
    for input_file, output_file in mapper:
        with open(input_file) as f:
            data = json.load(f)
            status = analyze_measurements(data,tagStruct, options.measurementsUnit, options.limbDifference)
            print(status)

def tagInfo_to_tagStruct(options):
    """
    Convert DICOM tag info in string to a dictionary.
    """
    if options.tagInfo:
        lstrip = lambda l: [x.strip() for x in l]

        # Split the string into key/value components
        l_sdirty: list = options.tagInfo.split(options.splitToken)

        # Now, strip any leading and trailing spaces from list elements
        l_s: list = lstrip(l_sdirty)
        d: dict = {}

        l_kvdirty: list = []
        l_kv: list = []
        try:
            for f in l_s:
                l_kvdirty = f.split(options.splitKeyValue)
                l_kv = lstrip(l_kvdirty)
                d[l_kv[0]] = l_kv[1]
        except:
            print('Incorrect tag info specified')
            return

        tagStruct = d.copy()
        return tagStruct

def analyze_measurements(data, tagStruct, unit, diff):
    """
    Analyze the measurements of lower limbs and verify
    if the measurements are correct.
    """
    status = {}
    details = {}
    measurements = {}
    for row in data:
        details = data[row]["details"]
        measurements = data[row]["total"]

    for row in tagStruct:
        try:
            if similar(tagStruct[row], details[row]) >= 0.8 or re.search(tagStruct[row], details[row],re.IGNORECASE):
                continue
            else:
                status['error'] = f"{row} does not match"
                status['exitCode'] = 1
                status['flag'] = False
                print(f"{row} does not match")
                return status
        except Exception as ex:
            status['error'] = f"{ex} not available for match."
            status['exitCode'] = 4
            status['flag'] = False
            print(f"{ex} not available for match.")
            return status
    if not unit in  measurements['Difference']:
        status['error'] = "Measurement units do not match."
        status['exitCode'] = 2
        status['flag'] = False
        print("Measurement units do not match.")
        return status

    match = re.search(r'\d.\d%',measurements['Difference']).group()
    difference = match.replace('%','')
    if not  float(difference) <= diff:
        status['error'] = f"Allowed difference {diff}, actual difference {difference}"
        status['exitCode'] = 3
        status['flag'] = False
        print(f"Allowed difference {diff}, actual difference {difference}")
        return status

    print("Analysis check successful.")
    status['error'] = ""
    status['exitCode'] = 0
    status['flag'] = True
    return status



def similar(a: str, b: str):
    """
    Return a similarity ration between two strings

    Examples:
    In [4]: similar("Apple","Appel")
    Out[4]: 0.8

    In [5]: similar("apple","apple")
    Out[5]: 1.0

    In [6]: similar("20/12/2024","2011212024")
    Out[6]: 0.8

    In [7]: similar("apple","dimple")
    Out[7]: 0.5454545454545454

    In [8]: similar("12/20/2024","2011012003")
    Out[8]: 0.4

    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


if __name__ == '__main__':
    main()
