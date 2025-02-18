# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from envcat import get_env_vars

from bedrock.base.models import ConfigValue
from bedrock.utils.git import GitRepo
from bedrock.utils.management.decorators import alert_sentry_on_exception


def get_config_file_name(app_name=None):
    app_name = app_name or settings.APP_NAME or "bedrock-dev"
    return os.path.join(settings.WWW_CONFIG_PATH, "waffle_configs", f"{app_name}.env")


def get_config_values():
    return get_env_vars(get_config_file_name())


def refresh_db_values():
    values = get_config_values()
    if not values:
        return 0

    ConfigValue.objects.all().delete()
    count = 0
    for name, value in values.items():
        if value:
            ConfigValue.objects.create(name=name, value=value)
            count += 1

    return count


@alert_sentry_on_exception
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-q", "--quiet", action="store_true", dest="quiet", default=False, help="If no error occurs, swallow all output."),
        parser.add_argument("-f", "--force", action="store_true", dest="force", default=False, help="Load the data even if nothing new from git."),

    def output(self, msg):
        if not self.quiet:
            print(msg)

    def handle(self, *args, **options):
        self.quiet = options["quiet"]
        repo = GitRepo(settings.WWW_CONFIG_PATH, settings.WWW_CONFIG_REPO, branch_name=settings.WWW_CONFIG_BRANCH, name="WWW Config")
        self.output("Updating git repo")
        repo.update()
        if not (options["force"] or repo.has_changes()):
            self.output("No config updates")
            return

        self.output("Loading configs into database")
        count = refresh_db_values()

        if count:
            self.output(f"{count} configs successfully loaded")
        else:
            self.output("No configs found. Please try again later.")

        repo.set_db_latest()

        self.output("Saved latest git repo state to database")
        self.output("Done!")
