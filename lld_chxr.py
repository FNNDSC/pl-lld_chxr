#!/usr/bin/env python

from pathlib import Path
from argparse import ArgumentParser, Namespace, ArgumentDefaultsHelpFormatter
from chris_plugin import chris_plugin, PathMapper
from difflib import SequenceMatcher
from shutil import copytree, ignore_patterns
from loguru import logger
from PIL import Image
import matplotlib.pyplot as plt
import numpy as np
import json
import subprocess
import re
import sys
import os
import shutil
import ntpath
import pydicom
import matplotlib


matplotlib.rcParams['font.family'] = 'monospace'
LOG             = logger.debug
logger_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> │ "
    "<level>{level: <5}</level> │ "
    "<yellow>{name: >28}</yellow>::"
    "<cyan>{function: <30}</cyan> @"
    "<cyan>{line: <4}</cyan> ║ "
    "<level>{message}</level>"
)
logger.remove()
logger.opt(colors = True)
logger.add(sys.stderr, format=logger_format)

__version__ = '1.2.2'

DISPLAY_TITLE = r"""
       _        _ _     _       _               
      | |      | | |   | |     | |              
 _ __ | |______| | | __| |  ___| |__ __  ___ __ 
| '_ \| |______| | |/ _` | / __| '_ \\ \/ / '__|
| |_) | |      | | | (_| || (__| | | |>  <| |   
| .__/|_|      |_|_|\__,_| \___|_| |_/_/\_\_|   
| |                    ______                   
|_|                   |______|                  
""" + "\t\t -- version " + __version__ + " --\n\n"

parser = ArgumentParser(
    description='A ChRIS plugin to analyze the result produced by an LLD analysis',
    formatter_class=ArgumentDefaultsHelpFormatter
)

# Input and filtering options
parser.add_argument(
    '-f', '--fileFilter',
    type=str,
    default='json',
    help='Input file filter glob'
)

# Measurement settings
parser.add_argument(
    '-m', '--measurementsUnit',
    type=str,
    default='',
    help='Accepted unit for length measurements'
)
parser.add_argument(
    '-d', '--limbDifference',
    type=float,
    default=sys.float_info.max,
    help='Accepted difference in both limbs'
)
parser.add_argument(
    '-b', '--tibiaDifference',
    type=float,
    default=sys.float_info.max,
    help='Accepted tibia difference in both limbs'
)
parser.add_argument(
    '-r', '--femurDifference',
    type=float,
    default=sys.float_info.max,
    help='Accepted femur difference in both limbs'
)

# Tag and key-value splitting
parser.add_argument(
    '-s', '--splitToken',
    type=str,
    default='',
    help='If specified, use this token to split the input tags.'
)
parser.add_argument(
    '-k', '--splitKeyValue',
    type=str,
    default='',
    help='If specified, use this char to split key-value.'
)
parser.add_argument(
    '-t', '--tagInfo',
    type=str,
    default='',
    help='Specify accepted tags and their values here.'
)

# Image output customization
parser.add_argument(
    '--outputImageExtension',
    dest='outputImageExtension',
    type=str,
    default='jpg',
    help='Generated output image file extension (default: jpg)'
)
parser.add_argument(
    '--addTextPos', '-q',
    dest='addTextPos',
    type=str,
    default='top',
    help='Position of text placement on an input image; "top" or "bottom"'
)
parser.add_argument(
    '--addText',
    dest='addText',
    type=str,
    default='',
    help='Optional text to add on the final image'
)
parser.add_argument(
    '--addTextSize',
    dest='addTextSize',
    type=float,
    default=5.0,
    help='Size of additional text on the final output (default: 5)'
)
parser.add_argument(
    '--addTextColor',
    dest='addTextColor',
    type=str,
    default='white',
    help='Color of additional text on the final output (default: white)'
)
parser.add_argument(
    '--addLineSpace',
    dest='addLineSpace',
    type=float,
    default=0.5,
    help='Line space in additional text on the final output, smaller = tighter (default: 0.5)'
)

# Version
parser.add_argument(
    '-V', '--version',
    action='version',
    version=f'%(prog)s {__version__}'
)

def preamble_show(options: Namespace) -> None:
    """
    Just show some preamble "noise" in the output terminal
    """
    LOG(DISPLAY_TITLE)
    LOG("plugin arguments...")
    for k,v in options.__dict__.items():
         LOG("%25s:  [%s]" % (k, v))
    LOG("")
    LOG("base environment...")
    for k,v in os.environ.items():
         LOG("%25s:  [%s]" % (k, v))
    LOG("")

# The main function of this *ChRIS* plugin is denoted by this ``@chris_plugin`` "decorator."
# Some metadata about the plugin is specified here. There is more metadata specified in setup.py.
#
# documentation: https://fnndsc.github.io/chris_plugin/chris_plugin.html#chris_plugin
@chris_plugin(
    parser=parser,
    title='A ChRIS plugin to analyze the result produced by an LLD analysis',
    category='',                 # ref. https://chrisstore.co/plugins
    min_memory_limit='1000Mi',    # supported units: Mi, Gi
    min_cpu_limit='4000m',       # millicores, e.g. "1000m" = 1 CPU core
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

    preamble_show(options)

    tagStruct = {}
    if options.tagInfo:
        tagStruct = tagInfo_to_tagStruct(options)
    mapper = PathMapper.file_mapper(inputdir, outputdir, glob=f"**/*{options.fileFilter}",fail_if_empty=False)
    for input_file, output_file in mapper:
        LOG(f"Reading input file {input_file}")
        filename = ntpath.basename(input_file)
        jsonFilePath = os.path.join(options.outputdir, filename.replace(options.fileFilter,"status.json"))
        with open(input_file) as f:
            data = json.load(f)
            status = analyze_measurements(data,tagStruct, options.measurementsUnit, options.limbDifference, options.tibiaDifference, options.femurDifference)
            if status['flag']:
                LOG("Analysis check successful.")
                files_dir = copytree(inputdir, outputdir,dirs_exist_ok=True,ignore=ignore_patterns('*.meta.json'))
                LOG(f"copying files to {files_dir} done.")
            else:
                LOG(f"QA check failed with exit code {status['exitCode']}")

                # save the original dicom file as image with error label
                matching_files = []
                for filename in os.listdir(inputdir):
                    if filename.endswith(".dcm"):
                        options.inputDicomFileName = filename
                        source = os.path.join(inputdir, filename)
                        destination = os.path.join(outputdir, filename)
                        shutil.copy(source, destination)
                        full_path = os.path.join(inputdir, filename)
                        matching_files.append(full_path)
                save_original_file(matching_files[0],options)

            # Open a json writer, and use the json.dumps()
            # function to dump data
            with open(jsonFilePath, 'w', encoding='utf-8') as jsonf:
                jsonf.write(json.dumps(status, indent=4))

def save_original_file(dicom_path, options):
    ds = read_dicom(dicom_path)
    image = dicom_to_image(ds)
    label_image(image, options)

def read_dicom(path):
    try:
        ds = pydicom.dcmread(path)
        return ds
    except Exception as e:
        LOG(f"Error reading DICOM file: {e}")
        return None

def dicom_to_image(ds):
    if not hasattr(ds, "PixelData"):
        print("No image data found in the DICOM file.")
        return None

    # normalize image
    img = ds.pixel_array.astype(float)
    img = (np.maximum(img, 0) / img.max()) * 255.0
    img = 255 - img  # Invert grayscale
    img = np.uint8(img)

    return img

def label_image(image_data, options):
    max_x, max_y = image_data.shape

    # Set up figure and draw image
    fig = setup_figure(image_data)

    # Scale annotation settings
    scale_annotations(fig, options)

    # Write text on image
    add_positioned_text(options, max_x, max_y)

    file_stem = options.inputDicomFileName.replace('.dcm','')
    # Save annotated figure to temporary image
    temp_img_path = f"/tmp/{file_stem}_img.jpg"
    save_figure_as_image(fig, temp_img_path)

    # Resize and rotate image
    final_img = resize_and_rotate_image(temp_img_path, target_width=image_data.shape[1])

    # Save final image to output directory
    output_img_path = os.path.join(options.outputdir, f"{file_stem}.{options.outputImageExtension}")
    save_image(final_img, output_img_path)

    LOG(f"Input image dimensions: {image_data.shape}")
    LOG(f"Output image dimensions: {final_img.size}")

def setup_figure(image: np.ndarray) -> plt.Figure:
    """
    Set up a matplotlib figure and display an image.

    Args:
        image (np.ndarray): Image array (e.g., from OpenCV).

    Returns:
        plt.Figure: Configured matplotlib figure.
    """
    plt.style.use('dark_background')
    plt.axis('off')
    height, width = image.shape
    fig = plt.figure(figsize=(width / 100, height / 100))
    plt.imshow(image, cmap='gray')
    return fig

def scale_annotations(fig: plt.Figure, options):
    """
    Scale annotation parameters (e.g., text, line width) based on image size.

    Args:
        fig (plt.Figure): Matplotlib figure object.
        options: Object with annotation settings to scale (e.g., textSize, lineGap).
    """
    scale = fig.get_size_inches()[0]
    options.addTextSize *= scale

def add_positioned_text(options, max_x, max_y):
    """
    Adds a text annotation to a matplotlib plot based on the specified position.

    Parameters:
    ----------
    options : object
        An object with the following required attributes:
            - addTextPos (str): Position of the text. Accepts "top" or "bottom".
            - addText (str): The text string to display.
            - addTextColor (str): Color of the text.
            - addTextSize (int or float): Font size of the text.
    max_x : int or float
        The maximum x-coordinate value for the plot area.
    max_y : int or float
        The maximum y-coordinate value for the plot area.

    Raises:
    ------
    ValueError:
        If `options.addTextPos` is not "top" or "bottom".
    """
    padding = 100
    if options.addTextPos == "top":
        x_pos, y_pos = padding, padding + options.addTextSize
    elif options.addTextPos == "bottom":
        x_pos, y_pos = padding, max_y - padding
    else:
        raise ValueError("Position must be 'top' or 'bottom'")

    # handles multiline text
    options.addText = options.addText.replace("\\n", "\n")

    plt.text(
        x_pos, y_pos, options.addText,
        color=options.addTextColor,
        fontsize=options.addTextSize,
        linespacing=options.addLineSpace
    )



def resize_and_rotate_image(image_path: str, target_width: int, rotate_angle: int = 0) -> Image.Image:
    """
    Resize and rotate an image to match a target width.

    Args:
        image_path (str): Path to input image.
        target_width (int): Desired output width.
        rotate_angle (int): Degrees to rotate image counter-clockwise.

    Returns:
        Image.Image: Resized and rotated image.
    """
    with Image.open(image_path) as img:
        original_width, original_height = img.size
        aspect_ratio = target_width / original_width
        new_size = (int(original_width * aspect_ratio), int(original_height * aspect_ratio))
        return img.resize(new_size).rotate(rotate_angle, expand=True)

def save_figure_as_image(fig: plt.Figure, output_path: str):
    """
    Save a matplotlib figure as an image file.

    Args:
        fig (plt.Figure): The figure to save.
        output_path (str): Target file path.
    """
    plt.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    fig.savefig(output_path, bbox_inches='tight', pad_inches=0)
    plt.clf()

def save_image(image: Image.Image, output_path: str):
    """
    Save a PIL Image to a specified path.

    Args:
        image (Image.Image): Image to save.
        output_path (str): Destination path including filename.
    """
    image.save(output_path)
    LOG(f"Saved image to {output_path}")

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
            LOG('Incorrect tag info specified')
            return

        tagStruct = d.copy()
        return tagStruct

def analyze_measurements(data, tagStruct, unit, tot_diff, tib_diff, fem_diff):
    """
    Analyze the measurements of lower limbs and verify
    if the measurements are correct.
    """
    status = {}
    details = {}
    femur = {}
    tibia = {}
    total = {}
    status['error'] = []
    status['exitCode'] = 0
    status['flag'] = True
    for row in data:
        details = data[row]["details"]
        femur = data[row]["femur"]
        tibia = data[row]["tibia"]
        total = data[row]["total"]

    for row in tagStruct:
        try:
            if similar(tagStruct[row], details[row]) >= 0.8 or re.search(tagStruct[row], details[row],re.IGNORECASE):
                continue
            else:
                status['error'].append(f"{row} does not match: Expected {tagStruct[row]}, actual {details[row]}")
                status['exitCode'] = 1
                status['flag'] = False
                LOG(f"{row} does not match: Expected {tagStruct[row]}, actual {details[row]}")
                #return status
        except Exception as ex:
            status['error'].append(f"{ex} not available for match.")
            status['exitCode'] = 4
            status['flag'] = False
            LOG(f"{ex} not available for match.")

    # check if the difference info contains measurements in the desired units.
    match = re.search(r'\d+ \w+', total['Difference']).group()
    m_unit = match.split()[1]
    if m_unit != unit:
        status['error'].append(f"Measurement units do not match: Expected {unit}, actual {m_unit}")
        status['exitCode'] = 2
        status['flag'] = False
        LOG(f"Measurement units do not match: Expected {unit}, actual {m_unit}")
        #return status

    # check if the difference info contains a float % representing limb difference.
    tibia_match = re.search(r'\d+\.\d+%',total['Difference']).group()
    total_difference = tibia_match.replace('%','')
    tibia_match = re.search(r'\d+\.\d+%', tibia['Difference']).group()
    tibia_difference = tibia_match.replace('%', '')
    femur_match = re.search(r'\d+\.\d+%', femur['Difference']).group()
    femur_difference = femur_match.replace('%', '')

    if ((float(total_difference) > tot_diff)
            or (float(femur_difference)  > fem_diff)
            or (float(tibia_difference) > tib_diff)):
        status['error'].append(f"Actual difference exceeds allowed difference")
        status['exitCode'] = 3
        status['flag'] = False
        LOG(f"Actual difference exceeds allowed difference")


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
