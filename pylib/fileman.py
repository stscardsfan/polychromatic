#!/usr/bin/python3
#
# Polychromatic is licensed under the GPLv3.
# Copyright (C) 2020 Luke Horwell <code@horwell.me>
#
"""
Provides a common class for handling save data across features of the
application that utilise individual JSON files, such as effects and presets.
"""

import glob
import json
import os

from . import common
from .preferences import VERSION as VERSION

# Error Codes
ERROR_NEWER_FORMAT = -1
ERROR_BAD_DATA = -2
ERROR_MISSING_FILE = -3
ERROR_NO_SCRIPT = -4


class FlatFileManagement(object):
    """
    Provides common functions for parsing a flat file structure of JSON files.
    This is used for storage for the application's feature offerings, such as
    effects and presets.
    """
    def __init__(self, i18n, _, dbg, ):
        """
        Store variables for the session.
        """
        self.i18n = i18n
        self._ = _
        self.dbg = dbg

        # Internal name of feature
        self.feature = "unknown"

        # Paths to where save data can be found for this feature.
        # "factory" refers to files the application ships by default.
        # "local" refers to files that the user created.
        self.factory_path = ""
        self.local_path = ""

    def _get_file_list(self):
        """
        Returns a list of JSON files.

        Each item consists of a dictionary:
        {
            "name": (str, localized),
            "icon": (str, absolute path),
            "path": (str, path to file),
            "type": (int, feature specific definition - e.g. effect type),
            "editable: (bool, can file be edited)
        }
        """
        file_list = []
        file_list += glob.glob(self.factory_path + "/*.json")
        file_list += glob.glob(self.local_path + "/*.json")
        return file_list

    def _load_file(self, file_path):
        """
        Load the JSON file into memory.

        Returns a dictionary containing the data, or None on failure.
        """
        data = {}

        if not os.path.exists(file_path):
            self.dbg.stdout("{0} no longer exists: {1}".format(self.feature.capitalize(), file_path), self.dbg.error)
            return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except json.decoder.JSONDecodeError as e:
            self.dbg.stdout("{0} contains invalid JSON: {1}\n{2}".format(self.feature.capitalize(), file_path, str(e)), self.dbg.error)
            return None

        return data

    def _get_i18n_key(self, data, key):
        """
        Returns a localized key if available.
        """
        localized_key_full = key + "_" + self.i18n.locale
        localized_key_partial = key + "_" + self.i18n.locale[:2]

        if localized_key_full in data.keys():
            return data[localized_key_full]

        if localized_key_partial in data.keys():
            return data[localized_key_partial]

        return data[key]

    def _get_icon(self, icon_path):
        """
        Returns the absolute path to the icon for use in the user interface.

        If the icon cannot be loaded, a fallback will be used.
        """
        possible_paths = []

        # It could already be an absolute path
        possible_paths.append(icon_path)

        # Try relative (custom) icons
        possible_paths.append(os.path.join(common.paths.custom_icons, icon_path))

        # Try relative (built-in) icons
        possible_paths.append(os.path.join(common.paths.data_dir, icon_path))

        for path in possible_paths:
            if os.path.exists(path):
                return path

        self.dbg.stdout("Could not locate suitable icon: '{0}'".format(icon_path), self.dbg.warning)
        return common.get_icon("emblems", "software")

    def _validate_key(self, data, key, data_type):
        """
        Returns a boolean to indicate whether the key has a value and matches the expected data type.
        """
        try:
            data[key]
        except KeyError:
            self.dbg.stdout("{0} file missing required key: {1} ({2})".format(self.feature.capitalize(), key, data_type), self.dbg.error)
            return False

        if type(data[key]) == data_type:
            return True

        return False

    def _get_parsed_keys(self, data, path):
        """
        Returns a dictionary with parsed values of the specified file. This is
        for use with user interface elements, like titles or lists.

        For example, this would be used to show the localised name and icon of
        an effect, as well as internal data like whether it's editable, the file path
        and effect type.
        """
        parsed = {}
        parsed["name"] = self._get_i18n_key(data, "name")
        parsed["icon"] = self._get_icon(data["icon"])
        parsed["type"] = data["type"]
        parsed["editable"] = os.access(path, os.W_OK)
        parsed["path"] = path
        return parsed

    def get_item_list(self):
        """
        Returns a list of parsed files for use with UI interaction, e.g. effect list
        on sidebar or CLI.
        """
        self.dbg.stdout("Loading list of {0}...".format(self.feature), self.dbg.action, 1)
        file_list = self._get_file_list()
        items = []

        for path in file_list:
            data = self._load_file(path)
            try:
                items.append(self._get_parsed_keys(data, path))
                self.dbg.stdout("- " + path, self.dbg.action, 1)
            except KeyError as e:
                self.dbg.stdout("Skipping invalid {0} file: {1}".format(self.feature, path), self.dbg.warning)

        return items

    def get_item(self, path):
        """
        Load the item into memory and ensure the data is up-to-date and consistent.
        The inheriting class should implement this accordingly.

        Returns:
            {}          Data for the feature as defined by the documentation.
            ERROR_*     One of ERROR_* variables in the root of this module.
        """
        raise NotImplementedError

    def upgrade_item(self, data):
        """
        Upgrades the data if it was saved in a older application version.
        The inheriting class should implement this accordingly.

        Returns the new data.
        """
        raise NotImplementedError

    def save_item(self, data, path):
        """
        Save the data to disk.

        Returns a boolean to indicate success or failure.
        """
        try:
            with open(path, "w+") as f:
                f.write(json.dumps(data, sort_keys=True, indent=4))
            return True
        except Exception as e:
            self.dbg.stdout("Failed to save " + path, self.dbg.error)
            self.dbg.stdout(common.get_exception_as_string(e), self.dbg.error)
            return False

    def init_new_item(self, item_type, item_name):
        """
        Initalize a new file for this feature.
        The inheriting class should implement this accordingly.

        Returns:
            (str)       File path (the application needs to know where to save later)
            None        File operation failed
        """
        raise NotImplementedError

    def rename_item(self, path, old_name, new_name):
        """
        Processes the rename of an item to keep the user's human name consistent
        with the file name. This will verify and update references from other files,
        such as effects <--> preset.

        Returns the file path so the application can update its save path in memory.
        """
        print("stub:fileman.rename_effect")
        pass
        #self.dbg.stdout("{0} renamed from '{1}' to '{2}'".format(self.feature.capitalize(), old_name, new_name), self.dbg.action, 1)

    def delete_item(self, path):
        """
        Processes the deletion of an item. This will verify and drop references
        from other files, such as a preset.

        Returns a boolean to indicate success.
        """
        try:
            os.remove(path)
        except Exception as e:
            self.dbg.stdout("Delete Failed: {0}\n{1}".format(path, common.get_exception_as_string(e)), self.dbg.error)

        if os.path.exists(path):
            return False

        self.dbg.stdout("Deleted: " + path, self.dbg.success, 1)
        return True

    def clone_item(self, path):
        """
        Processes the duplication of an item. This will append '(Copy)' for
        the user to modify later.

        Returns:
            (str)           Success: Path to the new file
            None            Failed to clone file
        """
        try:
            data = self._load_file(path)

            if not data:
                return None

            # Append "(Copy)" to name and "-copy" to filename
            data["name"] = self._("[] (Copy)").replace("[]", data["name"])
            new_path = path
            self.dbg.stdout("Determining clone filename...", self.dbg.debug, 1)
            while os.path.exists(new_path):
                new_path = new_path.replace(".json", "-copy.json")
            self.dbg.stdout("Copy will be saved as: " + new_path, self.dbg.debug, 1)

            if self.save_item(data, new_path):
                self.dbg.stdout("Clone OK: " + new_path, self.dbg.success)
                return new_path

        except Exception as e:
            self.dbg.stdout("Clone Failed: {0}\n{1}".format(path, common.get_exception_as_string(e)), self.dbg.error)

        return None
