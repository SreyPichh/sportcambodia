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

"""The runtime-configs create command."""

from googlecloudsdk.api_lib.deployment_manager.runtime_configs import util
from googlecloudsdk.calliope import base
from googlecloudsdk.core import log


class Create(base.CreateCommand):
  """Create runtime-config resources.

  This command creates a new runtime-config resource with the specified name
  and optional description.
  """

  detailed_help = {
      'DESCRIPTION': '{description}',
      'EXAMPLES': """\
          To create a runtime-config resource named "my-config", run:

            $ {command} my-config

          To create a runtime-config resource named "my-config" with a
          description, run:

            $ {command} --description "my new configuration" my-config
          """,
  }

  @staticmethod
  def Args(parser):
    """Args is called by calliope to gather arguments for this command.

    Args:
      parser: An argparse parser that you can use to add arguments that go
          on the command line after this command. Positional arguments are
          allowed.
    """
    parser.add_argument(
        '--description',
        help='Optional description of the runtime-config resource.')

    parser.add_argument('name', help='The runtime-config resource name.')

  def Collection(self):
    """Returns the default collection path string.

    Returns:
      The default collection path string.
    """
    return 'runtimeconfig.configurations'

  def Run(self, args):
    """Run 'runtime-configs create'.

    Args:
      args: argparse.Namespace, The arguments that this command was invoked
          with.

    Returns:
      The new runtime-config resource.

    Raises:
      HttpException: An http error response was received while executing api
          request.
    """
    config_client = util.ConfigClient()
    messages = util.Messages()

    config_resource = util.ParseConfigName(args.name)
    project = config_resource.projectsId
    name = config_resource.Name()

    result = config_client.Create(
        messages.RuntimeconfigProjectsConfigsCreateRequest(
            projectsId=project,
            runtimeConfig=messages.RuntimeConfig(
                name=util.ConfigPath(project, name),
                description=args.description,
            )
        )
    )

    log.CreatedResource(config_resource)
    return util.FormatConfig(result)
