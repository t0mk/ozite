#!/usr/bin/python

import sys
import os
import re
import stat
import argparse
import subprocess
import datetime
import tempfile
import shutil
import logging
import glance.client

logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s:%(name)s: %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

TMPROOT = "/var/tmp/"
MYNAME = os.path.basename(__file__)
DEFAULT_REPO = "http://gitgw.cern.ch/git/ai-image-templates"

DESCRIPTION = (
        "Based on oz template (tdl) and an unatended installation "
        "recipe, this script will generate images and upload them to glance. "
        "It expects the templates in a git repo or in a local dir. "
        "It is executing oz which in turn executes qemu-kvm => image generation" 
        "must be run with sudo. If you want to preserve environment variables "
        "in the sudo process, you must call sudo -E and have SETENV right in "
        "sudoers.")

EXAMPLES = """

Examples:

  - Create qcow2 image for slc5 from templates in git repo %(repo)s
    (it's the default repo):
        $ sudo -E %(name)s -d -n slc5 -f qcow2
    image with timestamp in the filename will be created in /tmp 
  
  - Create qcow2 image for slc5 from templates stored in cwd:
    (there must be slc5/slc5.{tdl,ks} in cwd)
        $ sudo %(name)s -d -n slc5 -l -f qcow2

  - Create image for slc5 from templates stored in git and upload it to glance
    with proper properties (-o parameter), with glance name "SLC5 image", to 
    tenant "tkarasek private" and then remove the generated image from local disk
        $ sudo -E %(name)s -d -n slc5 -p -u -d -o linux -g "SLC5 image" -t "tkarasek private"

  - Create image for slc5 from templates stored in git and upload it to glance
    with proper properties (-o parameter) and use credentials from file os_creds:
        $ sudo %(name)s -d -n slc5 -u -o linux -c ./os_creds -f qcow2
    *NOTE if you don't supply creds file, the script will use creds from
     current environment. That's why you must call sudo with -E. Also, you
     need to have SETENV in sudoers.

  - Upload image file /tmp/slc5.qcow2 to glance as Linxu image for tenant
    "tkarasek private":
        $ %(name)s -d -i /tmp/slc5.qcow2 -o linux -f qcow2 -t "tkarasek private"

  - Generate vhd image based on templates windows2012/windows2012.{xml,tdl},
    upload it to glance for tenant "tkarasek private", and delete the image 
    file from local disk.
        $ sudo -E %(name)s -d -n windows2012 -o windows -f vhd -u -p -t "tkarasek private"
""" % {'repo': DEFAULT_REPO, 'name': MYNAME}


_TEMPDIRS = []

#OSS = {
#    'SLC5': ("SCIENTIFIC LINUX CERN", "SLC5", "kvm"),
#    'SLC6': ("SCIENTIFIC LINUX CERN", "SLC6", "kvm"),
#    'SL6': ("SCIENTIFIC LINUX", "SL6", "kvm"),
#    'WINDOWS2012': ("WINDOWS 2012", "SERVER", "hyperv"),
#    'WINDOWS7': ("WINDOWS 7", "ENTERPRISE SP1", "hyperv"),
#    'WINDOWS2008': ("WINDOWS 2008", "SERVER R2 SP1", "hyperv")
#}

OSS = {
    'linux': ("LINUX", "kvm"),
    'windows': ("WINDOWS", "hyperv"),
}

IMAGE_FORMATS = {
    'qcow2': "qemu-img convert -p -c -O qcow2 {0} {1}",
    'vhd': "VBoxManage convertfromraw {0} {1} --format=VHD",
    'rawimg': "mv {0} {1}"
}


class GlanceProxy(object):
    _client = None
    def __new__(cls, *args, **kwargs):
        if not cls._client:
            cls._client = glance.client.get_client("0.0.0.0")
        return cls._client


class ImgGenError(Exception):
    pass


def argparseFile(f):
    if not os.path.isfile(f):
        raise Exception("%s is not a file" % f)
    return f


def getTempDir():
    d = tempfile.mkdtemp(dir=TMPROOT)
    mask = (stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | 
            stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
            stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)
    os.chmod(d,mask)
    logger.debug("Created tempdir %s" % d)
    _TEMPDIRS.append(d)
    return d


def cleanTemps():
    for d in _TEMPDIRS:
        logger.debug("Deleting tempdir %s" % d)
        shutil.rmtree(d)


def callCheck(command, env=None, stdin=None):
    logger.debug("about to run %s" % command)
    if subprocess.call(command, env=env, stdin=stdin):
        raise Exception("%s failed." % command)


def changeToTemplatesDir(name, local, repo):
    if not local:
        tempdir = getTempDir()
        os.chdir(tempdir)
        cmd_str = "git clone --depth 1 %s" % args.repo
        callCheck(cmd_str.split())
        os.chdir(os.path.basename(repo))

    template = "{0}/{0}.tdl".format(name) 
    if not os.path.isfile(template):
        raise ImgGenError("No %s in %s" % (template, os.getcwd()))


def generateImage(name, imgformat):
    tempdir = getTempDir()
    img = tempdir + "/%s.raw" % name
    oz_args = " -d 4 -s {0} {1}/{1}.tdl".format(img, name)
    for extension in ['ks', 'xml']:
        recipe = "{0}/{0}.{1}".format(name, extension) 
        if os.path.isfile(recipe):
            oz_args = (" -a %s " % recipe) + oz_args
            break
        else:
            logger.warn("no recipe %s found" % recipe)
    callCheck(("oz-install" + oz_args).split())

    converted_img = tempdir + "/{0}.{1}".format(name, imgformat)

    conv_cmd_str = IMAGE_FORMATS[imgformat].format(img, converted_img)

    callCheck(conv_cmd_str.split())
    pretty_name = "{0}-{1}.{2}".format(
        name, datetime.datetime.now().strftime("%Y%m%d-%H%M"), imgformat)
    exported_img = TMPROOT + pretty_name
    os.rename(converted_img, exported_img)
    return exported_img


def loadCreds(handle):
    pattern = re.compile(r"(export )?(\w+)=(.+)")
    cred_dict = {}
    for line in handle:
        if not line.strip():
            continue
        if line.lstrip().startswith("#"):
            continue
        (_, key, value) = pattern.match(line).groups()
        cred_dict[key] = value.strip().replace('\"','').replace('\'','')
    return cred_dict


def glanceGetImageIDforName(name):
    f = {'name': name}
    matching_imgs = GlanceProxy().get_images(filters=f)
    if matching_imgs:
        return matching_imgs[0]['id']
    else:
        return None


def glanceRemoveImage(img_id):
    logger.warn("Removing image with id %s" % img_id)
    GlanceProxy().delete_image(img_id)


def uploadImage(imgfile, imgformat, name, os_credentials=None, os_str=None):
    if not os_credentials:
        logger.warn("No file with Openstack credentials supplied, will "
                    "use whatever is in current env vars.")
    else:
        env_creds = loadCreds(os_credentials)
        os.environ.update(env_creds)
    if not name:
        name = os.path.basename(imgfile).rsplit(".",1)[0]

    img_id = glanceGetImageIDforName(name)
    if img_id:
        glanceRemoveImage(img_id)

    os_name, hypervisor_type = OSS[os_str]
    image_meta = {'name': name, 'is_public': False, 'disk_format': imgformat,
                  'container_format': 'bare',
                  'properties': {'os': os_name,
                    'hypervisor_type': hypervisor_type}}

    with open(imgfile) as image_data:
        GlanceProxy().add_image(image_meta, image_data)

def errorAndExit(message):
    logger.error(message)
    sys.exit(1)


if __name__ == "__main__":

    help_name = ("Name of tepmlate set to use. Must be present in a directory "
                 "either in a cwd or in given git repo.")
    help_local = ("Use template dir in cwd, dont clone a git repo.")
    help_repo = ("Git repo to get the templates from. Default is %s" %
                  DEFAULT_REPO)
    help_debug = ("Display debug messages.")
    help_os = ("OS to claim to landb.")
    help_upload_generated_image = ("Upload the generated image to glance.")
    help_upload_existing_image = ("Upload given image file to glance.")
    help_os_credentials = ("file with key=value lines of openstack "
        "credentials. Use this when you want to upload image to Glance "
        "and you can't/don't_want_to use credentials from current environment "
        "variables.")
    help_image_format = ("Format of disk image.")
    help_tenant = ("Openstack tenant to upload the image to.")
    help_glance_name = ("A string to name the image in glance.")
    help_purge = ("Remove image file after it was uploaded to glance from "
                  "local disk.")

    parser = argparse.ArgumentParser(description=DESCRIPTION + EXAMPLES,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-n', '--name', required=False, help=help_name)
    parser.add_argument('-r', '--repo', required=False,
        default=DEFAULT_REPO, help=help_repo)
    parser.add_argument('-g', '--glance_name', required=False,
        help=help_glance_name)
    parser.add_argument('-l', '--local', default=False, action="store_true",
        help=help_local)
    parser.add_argument('-p', '--purge', default=False, action="store_true",
        help=help_purge)
    parser.add_argument('-d', '--debug', default=False, action="store_true",
        help=help_debug)
    parser.add_argument('-u', '--upload_generated_image', default=False,
        action="store_true", help=help_upload_generated_image)
    parser.add_argument('-i', '--upload_existing_image', required=False,
        type=argparseFile, help=help_upload_existing_image,
        metavar="image_file")
    parser.add_argument('-o', '--os', required=False, choices=OSS.keys(),
        help=help_os)
    parser.add_argument('-f', '--image_format', required=True, 
        choices=IMAGE_FORMATS.keys(), help=help_image_format)
    parser.add_argument('-t', '--tenant', required=False, help=help_tenant)
    parser.add_argument('-c', '--os_credentials', required=False,
        type=argparse.FileType('r'), help=help_os_credentials,
        metavar="file_with_credentials")

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)

    # resolving argument conflicts
    if args.upload_existing_image:
        if args.name or args.local:
            errorAndExit("There is no point passing --name, --repo or --local "
                         "when you only want to upload existing image")
        
    if args.upload_generated_image or args.upload_existing_image:
        # arguments check for the case of uploading images
        if not args.os:
            errorAndExit("If you want to upload the image to glance, you must "
                         "supply the OS version in -o|--os.")
        if args.os_credentials and args.tenant:
            errorAndExit("Don't pass -t/--tenant when supplying Openstack "
                         "credentials from a file. Rather specify it in the "
                         "file as OS_TENANT_NAME.")
        if not args.os_credentials and not args.tenant:
            errorAndExit("You must set either -t/--tenant or "
                        "-c/--os_credentials when you upload image to "
                        "Openstack.")

        # set OS_TENANT_NAME environment variable
        logger.debug("Setting OS_TENANT_NAME env var to %s" % args.tenant)
        os.environ['OS_TENANT_NAME'] = args.tenant

        # check we can connect to Glance before starting to do the work
        try:
            GlanceProxy().get_images()
        except:
            errorAndExit("Can't connect to Glance. Is the tenant set properly?")
    else:
        # arguments check for local creation only
        if args.tenant:
            errorAndExit("There is no point passing Openstack tenant "
                         "(--tenant/-t) when you don't intend to upload the "
                         "image to glance..")
        if args.purge:
            errorAndExit("There is no point to --purge/-p image when you "
                         "don't intend to upload the image to glance..")
        if args.glance_name:
            errorAndExit("There is no point passing --glance_name/-g image "
                         " when you don't intend to upload the image to glance.")
        if args.os:
            errorAndExit("There is no point passing --os/-o"
                         " when you don't intend to upload the image to glance.")

    if not args.upload_existing_image and not args.name:
        errorAndExit("You must pass a --name if you want to generate image.")


    try:
        converted_img = ""
        if not args.upload_existing_image:
            changeToTemplatesDir(args.name, args.local, args.repo)
            converted_img = generateImage(args.name, args.image_format)
            print ("New image in %s" % converted_img)
        else:
            converted_img = args.upload_existing_image
        if args.upload_generated_image or args.upload_existing_image:
            uploadImage(converted_img, args.image_format, args.glance_name,
                os_credentials=args.os_credentials, os_str=args.os)
    finally:
        if args.purge and os.path.isfile(converted_img):
            print "Deleting image file %s" % converted_img
            os.remove(converted_img)
        cleanTemps()

