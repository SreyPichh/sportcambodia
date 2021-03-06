# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The gcloud error-reporting events report command."""

from googlecloudsdk.api_lib.error_reporting import util
from googlecloudsdk.calliope import base
from googlecloudsdk.core import exceptions
from googlecloudsdk.core import log
from googlecloudsdk.core import properties


class CannotOpenFileError(exceptions.Error):

  def __init__(self, f, e):
    super(CannotOpenFileError, self).__init__(
        'Failed to open file [{f}]: {error}'.format(f=f, error=e))


class Report(base.Command):
  """Report an error.

  {command} is used to report errors using the error-reporting service.
  The required arguments are a service name and either an
  error-file containing details of an error or an inline error message.

  ## EXAMPLES

  To report an error, run:

    $ {command} --service service-name --message error-message

  or:

    $ {command} --service service-name --message-file error-message.ext.
  """

  @staticmethod
  def Args(parser):
    """Get arguments for this command.

    Args:
      parser: argparse.ArgumentParser, the parser for this command.
    """
    parser.add_argument(
        '--service',
        required=True,
        help='The name of the service that generated the error')
    parser.add_argument(
        '--service-version',
        help='The release version of the service')

    # add mutually exclusive arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--message',
        help='Inline details of the error')
    group.add_argument(
        '--message-file',
        help='File containing details of the error')

  def GetMessage(self, args):
    """Get error message.

    Args:
      args: the arguments for the command

    Returns:
      error_message read from error file or provided inline

    Raises:
      CannotOpenFileError: When there is a problem with reading the file
    """
    if args.message_file:
      try:
        error = open(args.message_file, 'r')
      except (OSError, IOError) as e:
        raise CannotOpenFileError(args.message_file, e)
      error_message = error.read()
    elif args.message:
      error_message = args.message
    return error_message

  def GetProject(self, args):
    """Get project name."""
    return properties.VALUES.core.project.Get(required=True)

  def Run(self, args):
    """Send an error report based on the given args."""

    # Get required message components for API report request
    error_message = self.GetMessage(args)
    service = args.service
    # Get service version if provided, otherwise service_version=None
    service_version = args.service_version
    project = self.GetProject(args)

    # Send error report
    error_event = util.ErrorReporting()
    error_event.ReportEvent(error_message, service, service_version, project)

    log.status.Print('Your error has been reported.')

