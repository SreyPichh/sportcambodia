# -*- coding: utf-8 -*-
# Copyright 2011 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Implementation of Unix-like ls command for cloud storage providers."""

from __future__ import absolute_import

import re

from gslib.boto_translation import S3_DELETE_MARKER_GUID
from gslib.cloud_api import NotFoundException
from gslib.command import Command
from gslib.command_argument import CommandArgument
from gslib.cs_api_map import ApiSelector
from gslib.exception import CommandException
from gslib.ls_helper import ENCRYPTED_FIELDS
from gslib.ls_helper import LsHelper
from gslib.ls_helper import UNENCRYPTED_FULL_LISTING_FIELDS
from gslib.storage_url import ContainsWildcard
from gslib.storage_url import StorageUrlFromString
from gslib.translation_helper import AclTranslation
from gslib.util import ListingStyle
from gslib.util import MakeHumanReadable
from gslib.util import NO_MAX
from gslib.util import PrintFullInfoAboutObject
from gslib.util import UTF8


# Regex that assists with converting JSON timestamp to ls-style output.
# This excludes timestamp fractional seconds, for example:
# 2013-07-03 20:32:53.048000+00:00
JSON_TIMESTAMP_RE = re.compile(r'([^\s]*)\s([^\.\+]*).*')

_SYNOPSIS = """
  gsutil ls [-a] [-b] [-d] [-l] [-L] [-r] [-p proj_id] url...
"""

_DETAILED_HELP_TEXT = ("""
<B>SYNOPSIS</B>
""" + _SYNOPSIS + """


<B>LISTING PROVIDERS, BUCKETS, SUBDIRECTORIES, AND OBJECTS</B>
  If you run gsutil ls without URLs, it lists all of the Google Cloud Storage
  buckets under your default project ID:

    gsutil ls

  (For details about projects, see "gsutil help projects" and also the -p
  option in the OPTIONS section below.)

  If you specify one or more provider URLs, gsutil ls will list buckets at
  each listed provider:

    gsutil ls gs://

  If you specify bucket URLs, gsutil ls will list objects at the top level of
  each bucket, along with the names of each subdirectory. For example:

    gsutil ls gs://bucket

  might produce output like:

    gs://bucket/obj1.htm
    gs://bucket/obj2.htm
    gs://bucket/images1/
    gs://bucket/images2/

  The "/" at the end of the last 2 URLs tells you they are subdirectories,
  which you can list using:

    gsutil ls gs://bucket/images*

  If you specify object URLs, gsutil ls will list the specified objects. For
  example:

    gsutil ls gs://bucket/*.txt

  will list all files whose name matches the above wildcard at the top level
  of the bucket.

  See "gsutil help wildcards" for more details on working with wildcards.


<B>DIRECTORY BY DIRECTORY, FLAT, and RECURSIVE LISTINGS</B>
  Listing a bucket or subdirectory (as illustrated near the end of the previous
  section) only shows the objects and names of subdirectories it contains. You
  can list all objects in a bucket by using the -r option. For example:

    gsutil ls -r gs://bucket

  will list the top-level objects and buckets, then the objects and
  buckets under gs://bucket/images1, then those under gs://bucket/images2, etc.

  If you want to see all objects in the bucket in one "flat" listing use the
  recursive ("**") wildcard, like:

    gsutil ls -r gs://bucket/**

  or, for a flat listing of a subdirectory:

    gsutil ls -r gs://bucket/dir/**

  If you want to see only the subdirectory itself, use the -d option:

    gsutil ls -d gs://bucket/dir


<B>LISTING OBJECT DETAILS</B>
  If you specify the -l option, gsutil will output additional information
  about each matching provider, bucket, subdirectory, or object. For example:

    gsutil ls -l gs://bucket/*.txt

  will print the object size, creation time stamp, and name of each matching
  object, along with the total count and sum of sizes of all matching objects:

       2276224  2012-03-02T19:25:17Z  gs://bucket/obj1
       3914624  2012-03-02T19:30:27Z  gs://bucket/obj2
    TOTAL: 2 objects, 6190848 bytes (5.9 MiB)

  Note that the total listed in parentheses above is in mebibytes (or gibibytes,
  tebibytes, etc.), which corresponds to the unit of billing measurement for
  Google Cloud Storage.

  You can get a listing of all the objects in the top-level bucket directory
  (along with the total count and sum of sizes) using a command like:

    gsutil ls -l gs://bucket

  To print additional detail about objects and buckets use the gsutil ls -L
  option. For example:

    gsutil ls -L gs://bucket/obj1

  will print something like:

    gs://bucket/obj1:
            Creation time:      Fri, 02 Mar 2012 19:25:17 GMT
            Update time:        Fri, 04 Mar 2012 11:39:24 GMT
            Size:               2276224
            Cache-Control:      private, max-age=0
            Content-Type:       application/x-executable
            ETag:               5ca6796417570a586723b7344afffc81
            Generation:         1378862725952000
            Metageneration:     1
            ACL:
    [
      {
        "entity": "group-00b4903a97163d99003117abe64d292561d2b4074fc90ce5c0e35ac45f66ad70",
        "entityId": "00b4903a97163d99003117abe64d292561d2b4074fc90ce5c0e35ac45f66ad70",
        "role": "OWNER"
      }
    ]
    TOTAL: 1 objects, 2276224 bytes (2.17 MiB)

  Note that the Update time field above is not available with the (non-default)
  XML API.

  See also "gsutil help acl" for getting a more readable version of the ACL.


<B>LISTING BUCKET DETAILS</B>
  If you want to see information about the bucket itself, use the -b
  option. For example:

    gsutil ls -L -b gs://bucket

  will print something like:

    gs://bucket/ :
            Storage class:                MULTI_REGIONAL
            Location constraint:          US
            Versioning enabled:           True
            Logging configuration:        None
            Website configuration:        None
            CORS configuration:           Present
            Lifecycle configuration:      None
            Time created:                 Fri, 21 Oct 2016 19:25:17 GMT
            Time updated:                 Fri, 21 Oct 2016 21:17:59 GMT
    [
      {
        "entity": "group-00b4903a97163d99003117abe64d292561d2b4074fc90ce5c0e35ac45f66ad70",
        "entityId": "00b4903a97163d99003117abe64d292561d2b4074fc90ce5c0e35ac45f66ad70",
        "role": "OWNER"
      }
    ]
            Default ACL:
    [
      {
        "entity": "group-00b4903a97163d99003117abe64d292561d2b4074fc90ce5c0e35ac45f66ad70",
        "entityId": "00b4903a97163d99003117abe64d292561d2b4074fc90ce5c0e35ac45f66ad70",
        "role": "OWNER"
      }
    ]

  Note that the Time created and Time updated fields above are not available
  with the (non-default) XML API.


<B>OPTIONS</B>
  -l          Prints long listing (owner, length).

  -L          Prints even more detail than -l.  Note: If you use this option
              with the (non-default) XML API it will generate an additional
              request per object being listed, which makes the -L option run
              much more slowly (and cost more) using the XML API than the
              default JSON API.

  -d          List matching subdirectory names instead of contents, and do not
              recurse into matching subdirectories even if the -R option is
              specified.

  -b          Prints info about the bucket when used with a bucket URL.

  -h          When used with -l, prints object sizes in human readable format
              (e.g., 1 KiB, 234 MiB, 2 GiB, etc.)

  -p proj_id  Specifies the project ID to use for listing buckets.

  -R, -r      Requests a recursive listing.

  -a          Includes non-current object versions / generations in the listing
              (only useful with a versioning-enabled bucket). If combined with
              -l option also prints metageneration for each listed object.

  -e          Include ETag in long listing (-l) output.
""")


class LsCommand(Command):
  """Implementation of gsutil ls command."""

  # Command specification. See base class for documentation.
  command_spec = Command.CreateCommandSpec(
      'ls',
      command_name_aliases=['dir', 'list'],
      usage_synopsis=_SYNOPSIS,
      min_args=0,
      max_args=NO_MAX,
      supported_sub_args='aebdlLhp:rR',
      file_url_ok=False,
      provider_url_ok=True,
      urls_start_arg=0,
      gs_api_support=[ApiSelector.XML, ApiSelector.JSON],
      gs_default_api=ApiSelector.JSON,
      argparse_arguments=[
          CommandArgument.MakeZeroOrMoreCloudURLsArgument()
      ]
  )
  # Help specification. See help_provider.py for documentation.
  help_spec = Command.HelpSpec(
      help_name='ls',
      help_name_aliases=['dir', 'list'],
      help_type='command_help',
      help_one_line_summary='List providers, buckets, or objects',
      help_text=_DETAILED_HELP_TEXT,
      subcommand_help_text={},
  )

  def _PrintBucketInfo(self, bucket_blr, listing_style):
    """Print listing info for given bucket.

    Args:
      bucket_blr: BucketListingReference for the bucket being listed
      listing_style: ListingStyle enum describing type of output desired.

    Returns:
      Tuple (total objects, total bytes) in the bucket.
    """
    if (listing_style == ListingStyle.SHORT or
        listing_style == ListingStyle.LONG):
      print bucket_blr
      return
    # listing_style == ListingStyle.LONG_LONG:
    # We're guaranteed by the caller that the root object is populated.
    bucket = bucket_blr.root_object
    location_constraint = bucket.location
    storage_class = bucket.storageClass
    fields = {'bucket': bucket_blr.url_string,
              'storage_class': storage_class,
              'location_constraint': location_constraint,
              'acl': AclTranslation.JsonFromMessage(bucket.acl),
              'default_acl': AclTranslation.JsonFromMessage(
                  bucket.defaultObjectAcl)}

    fields['versioning'] = bucket.versioning and bucket.versioning.enabled
    fields['website_config'] = 'Present' if bucket.website else 'None'
    fields['logging_config'] = 'Present' if bucket.logging else 'None'
    fields['cors_config'] = 'Present' if bucket.cors else 'None'
    fields['lifecycle_config'] = 'Present' if bucket.lifecycle else 'None'
    if bucket.timeCreated:
      fields['time_created'] = bucket.timeCreated.strftime(
          '%a, %d %b %Y %H:%M:%S GMT')
    if bucket.updated:
      fields['updated'] = bucket.updated.strftime('%a, %d %b %Y %H:%M:%S GMT')

    # For field values that are multiline, add indenting to make it look
    # prettier.
    for key in fields:
      previous_value = fields[key]
      if (not isinstance(previous_value, basestring) or
          '\n' not in previous_value):
        continue
      new_value = previous_value.replace('\n', '\n\t  ')
      # Start multiline values on a new line if they aren't already.
      if not new_value.startswith('\n'):
        new_value = '\n\t  ' + new_value
      fields[key] = new_value

    # Only display time-related properties if the given API returned them.
    time_created_line = ''
    time_updated_line = ''
    if 'time_created' in fields:
      time_created_line = '\tTime created:\t\t\t{time_created}\n'
    if 'updated' in fields:
      time_updated_line = '\tTime updated:\t\t\t{updated}\n'

    print(('{bucket} :\n'
           '\tStorage class:\t\t\t{storage_class}\n'
           '\tLocation constraint:\t\t{location_constraint}\n'
           '\tVersioning enabled:\t\t{versioning}\n'
           '\tLogging configuration:\t\t{logging_config}\n'
           '\tWebsite configuration:\t\t{website_config}\n'
           '\tCORS configuration: \t\t{cors_config}\n'
           '\tLifecycle configuration:\t{lifecycle_config}\n' +
           time_created_line +
           time_updated_line +
           '\tACL:\t\t\t\t{acl}\n'
           '\tDefault ACL:\t\t\t{default_acl}').format(**fields))
    if bucket_blr.storage_url.scheme == 's3':
      print('Note: this is an S3 bucket so configuration values may be '
            'blank. To retrieve bucket configuration values, use '
            'individual configuration commands such as gsutil acl get '
            '<bucket>.')

  def _PrintLongListing(self, bucket_listing_ref):
    """Prints an object with ListingStyle.LONG."""
    obj = bucket_listing_ref.root_object
    url_str = bucket_listing_ref.url_string
    if (obj.metadata and S3_DELETE_MARKER_GUID in
        obj.metadata.additionalProperties):
      size_string = '0'
      num_bytes = 0
      num_objs = 0
      url_str += '<DeleteMarker>'
    else:
      size_string = (MakeHumanReadable(obj.size)
                     if self.human_readable else str(obj.size))
      num_bytes = obj.size
      num_objs = 1

    timestamp = JSON_TIMESTAMP_RE.sub(
        r'\1T\2Z', str(obj.timeCreated).decode(UTF8).encode('ascii'))
    printstr = '%(size)10s  %(timestamp)s  %(url)s'
    encoded_etag = None
    encoded_metagen = None
    if self.all_versions:
      printstr += '  metageneration=%(metageneration)s'
      encoded_metagen = str(obj.metageneration).encode(UTF8)
    if self.include_etag:
      printstr += '  etag=%(etag)s'
      encoded_etag = obj.etag.encode(UTF8)
    format_args = {
        'size': size_string,
        'timestamp': timestamp,
        'url': url_str.encode(UTF8),
        'metageneration': encoded_metagen,
        'etag': encoded_etag
    }
    print printstr % format_args
    return (num_objs, num_bytes)

  def RunCommand(self):
    """Command entry point for the ls command."""
    got_nomatch_errors = False
    got_bucket_nomatch_errors = False
    listing_style = ListingStyle.SHORT
    get_bucket_info = False
    self.recursion_requested = False
    self.all_versions = False
    self.include_etag = False
    self.human_readable = False
    self.list_subdir_contents = True
    if self.sub_opts:
      for o, a in self.sub_opts:
        if o == '-a':
          self.all_versions = True
        elif o == '-e':
          self.include_etag = True
        elif o == '-b':
          get_bucket_info = True
        elif o == '-h':
          self.human_readable = True
        elif o == '-l':
          listing_style = ListingStyle.LONG
        elif o == '-L':
          listing_style = ListingStyle.LONG_LONG
        elif o == '-p':
          self.project_id = a
        elif o == '-r' or o == '-R':
          self.recursion_requested = True
        elif o == '-d':
          self.list_subdir_contents = False

    if not self.args:
      # default to listing all gs buckets
      self.args = ['gs://']

    total_objs = 0
    total_bytes = 0

    def MaybePrintBucketHeader(blr):
      if len(self.args) > 1:
        print '%s:' % blr.url_string.encode(UTF8)
    print_bucket_header = MaybePrintBucketHeader

    for url_str in self.args:
      storage_url = StorageUrlFromString(url_str)
      if storage_url.IsFileUrl():
        raise CommandException('Only cloud URLs are supported for %s'
                               % self.command_name)
      bucket_fields = None
      if (listing_style == ListingStyle.SHORT or
          listing_style == ListingStyle.LONG):
        bucket_fields = ['id']
      elif listing_style == ListingStyle.LONG_LONG:
        bucket_fields = ['location', 'storageClass', 'versioning', 'acl',
                         'defaultObjectAcl', 'website', 'logging', 'cors',
                         'lifecycle', 'timeCreated', 'updated']
      if storage_url.IsProvider():
        # Provider URL: use bucket wildcard to list buckets.
        for blr in self.WildcardIterator(
            '%s://*' % storage_url.scheme).IterBuckets(
                bucket_fields=bucket_fields):
          self._PrintBucketInfo(blr, listing_style)
      elif storage_url.IsBucket() and get_bucket_info:
        # ls -b bucket listing request: List info about bucket(s).
        total_buckets = 0
        for blr in self.WildcardIterator(url_str).IterBuckets(
            bucket_fields=bucket_fields):
          if not ContainsWildcard(url_str) and not blr.root_object:
            # Iterator does not make an HTTP call for non-wildcarded
            # listings with fields=='id'. Ensure the bucket exists by calling
            # GetBucket.
            self.gsutil_api.GetBucket(
                blr.storage_url.bucket_name,
                fields=['id'], provider=storage_url.scheme)
          self._PrintBucketInfo(blr, listing_style)
          total_buckets += 1
        if not ContainsWildcard(url_str) and not total_buckets:
          got_bucket_nomatch_errors = True
      else:
        # URL names a bucket, object, or object subdir ->
        # list matching object(s) / subdirs.
        def _PrintPrefixLong(blr):
          print '%-33s%s' % ('', blr.url_string.encode(UTF8))

        if listing_style == ListingStyle.SHORT:
          # ls helper by default readies us for a short listing.
          ls_helper = LsHelper(self.WildcardIterator, self.logger,
                               all_versions=self.all_versions,
                               print_bucket_header_func=print_bucket_header,
                               should_recurse=self.recursion_requested,
                               list_subdir_contents=self.list_subdir_contents)
        elif listing_style == ListingStyle.LONG:
          bucket_listing_fields = ['name', 'timeCreated', 'updated', 'size']
          if self.all_versions:
            bucket_listing_fields.extend(['generation', 'metageneration'])
          if self.include_etag:
            bucket_listing_fields.append('etag')

          ls_helper = LsHelper(self.WildcardIterator, self.logger,
                               print_object_func=self._PrintLongListing,
                               print_dir_func=_PrintPrefixLong,
                               print_bucket_header_func=print_bucket_header,
                               all_versions=self.all_versions,
                               should_recurse=self.recursion_requested,
                               fields=bucket_listing_fields,
                               list_subdir_contents=self.list_subdir_contents)

        elif listing_style == ListingStyle.LONG_LONG:
          # List all fields
          bucket_listing_fields = (UNENCRYPTED_FULL_LISTING_FIELDS +
                                   ENCRYPTED_FIELDS)
          ls_helper = LsHelper(self.WildcardIterator, self.logger,
                               print_object_func=PrintFullInfoAboutObject,
                               print_dir_func=_PrintPrefixLong,
                               print_bucket_header_func=print_bucket_header,
                               all_versions=self.all_versions,
                               should_recurse=self.recursion_requested,
                               fields=bucket_listing_fields,
                               list_subdir_contents=self.list_subdir_contents)
        else:
          raise CommandException('Unknown listing style: %s' % listing_style)

        exp_dirs, exp_objs, exp_bytes = ls_helper.ExpandUrlAndPrint(storage_url)
        if storage_url.IsObject() and exp_objs == 0 and exp_dirs == 0:
          got_nomatch_errors = True
        total_bytes += exp_bytes
        total_objs += exp_objs

    if total_objs and listing_style != ListingStyle.SHORT:
      print ('TOTAL: %d objects, %d bytes (%s)' %
             (total_objs, total_bytes, MakeHumanReadable(float(total_bytes))))
    if got_nomatch_errors:
      raise CommandException('One or more URLs matched no objects.')
    if got_bucket_nomatch_errors:
      raise NotFoundException('One or more bucket URLs matched no buckets.')

    return 0
