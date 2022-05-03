#!/usr/bin/env python3
"""
BORIS
Behavioral Observation Research Interactive Software
Copyright 2012-2022 Olivier Friard

This file is part of BORIS.

  BORIS is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 3 of the License, or
  any later version.

  BORIS is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not see <http://www.gnu.org/licenses/>.

"""

import json
import logging
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import tablib
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSpacerItem,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QSizePolicy,
    QMessageBox,
    QLineEdit,
    QFileDialog,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QMenu,
)

from . import add_modifier
from . import config as cfg
from . import dialog, exclusion_matrix, export_observation, project_import
from . import converters

from .project_ui import Ui_dlgProject


class BehavioralCategories(QDialog):
    def __init__(self, pj):
        super().__init__()

        self.pj = pj
        self.setWindowTitle("Behavioral categories")

        self.renamed = None
        self.removed = None

        self.vbox = QVBoxLayout(self)

        self.label = QLabel()
        self.label.setText("Behavioral categories")
        self.vbox.addWidget(self.label)

        self.lw = QListWidget()

        if cfg.BEHAVIORAL_CATEGORIES in pj:
            for category in pj[cfg.BEHAVIORAL_CATEGORIES]:
                self.lw.addItem(QListWidgetItem(category))

        self.vbox.addWidget(self.lw)

        self.hbox0 = QHBoxLayout(self)
        self.pbAddCategory = QPushButton("Add category")
        self.pbAddCategory.clicked.connect(self.pbAddCategory_clicked)
        self.pbRemoveCategory = QPushButton("Remove category")
        self.pbRemoveCategory.clicked.connect(self.pbRemoveCategory_clicked)
        self.pb_rename_category = QPushButton("Rename category")
        self.pb_rename_category.clicked.connect(self.pb_rename_category_clicked)

        spacerItem = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.hbox0.addItem(spacerItem)
        self.hbox0.addWidget(self.pb_rename_category)
        self.hbox0.addWidget(self.pbRemoveCategory)
        self.hbox0.addWidget(self.pbAddCategory)
        self.vbox.addLayout(self.hbox0)

        hbox1 = QHBoxLayout(self)
        self.pbOK = QPushButton("OK")
        self.pbOK.clicked.connect(self.accept)
        self.pbCancel = QPushButton("Cancel")
        self.pbCancel.clicked.connect(self.reject)
        spacerItem = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        hbox1.addItem(spacerItem)
        hbox1.addWidget(self.pbCancel)
        hbox1.addWidget(self.pbOK)
        self.vbox.addLayout(hbox1)

        self.setLayout(self.vbox)

    def pbAddCategory_clicked(self):
        """
        add a behavioral category
        """
        category, ok = QInputDialog.getText(self, "New behavioral category", "Category name:")
        if ok:
            self.lw.addItem(QListWidgetItem(category))

    def pbRemoveCategory_clicked(self):
        """
        remove the selected behavioral category
        """

        for SelectedItem in self.lw.selectedItems():
            # check if behavioral category is in use
            category_to_remove = self.lw.item(self.lw.row(SelectedItem)).text().strip()
            behaviors_in_category = []
            for idx in self.pj[cfg.ETHOGRAM]:
                if (
                    cfg.BEHAVIOR_CATEGORY in self.pj[cfg.ETHOGRAM][idx]
                    and self.pj[cfg.ETHOGRAM][idx][cfg.BEHAVIOR_CATEGORY] == category_to_remove
                ):
                    behaviors_in_category.append(self.pj[cfg.ETHOGRAM][idx][cfg.BEHAVIOR_CODE])
            flag_remove = False
            if behaviors_in_category:

                flag_remove = (
                    dialog.MessageDialog(
                        cfg.programName,
                        (
                            "Some behavior belong to the <b>{1}</b> to remove:<br>"
                            "{0}<br>"
                            "<br>Some features may not be available anymore.<br>"
                        ).format("<br>".join(behaviors_in_category), category_to_remove),
                        ["Remove category", cfg.CANCEL],
                    )
                    == "Remove category"
                )

            else:
                flag_remove = True

            if flag_remove:
                self.lw.takeItem(self.lw.row(SelectedItem))
                self.removed = category_to_remove
                self.accept()

    def pb_rename_category_clicked(self):
        """
        rename the selected behavioral category
        """
        for SelectedItem in self.lw.selectedItems():
            # check if behavioral category is in use
            category_to_rename = self.lw.item(self.lw.row(SelectedItem)).text().strip()
            behaviors_in_category = []
            for idx in self.pj[cfg.ETHOGRAM]:
                if (
                    cfg.BEHAVIOR_CATEGORY in self.pj[cfg.ETHOGRAM][idx]
                    and self.pj[cfg.ETHOGRAM][idx][cfg.BEHAVIOR_CATEGORY] == category_to_rename
                ):
                    behaviors_in_category.append(self.pj[cfg.ETHOGRAM][idx][cfg.BEHAVIOR_CODE])

            flag_rename = False
            if behaviors_in_category:
                flag_rename = (
                    dialog.MessageDialog(
                        cfg.programName,
                        ("Some behavior belong to the <b>{1}</b> to rename:<br>" "{0}<br>").format(
                            "<br>".join(behaviors_in_category), category_to_rename
                        ),
                        ["Rename category", cfg.CANCEL],
                    )
                    == "Rename category"
                )
            else:
                flag_rename = True

            if flag_rename:
                new_category_name, ok = QInputDialog.getText(
                    self, "Rename behavioral category", "New category name:", QLineEdit.Normal, category_to_rename
                )
                if ok:
                    self.lw.item(self.lw.indexFromItem(SelectedItem).row()).setText(new_category_name)
                    # check behaviors belonging to the renamed category
                    self.renamed = [category_to_rename, new_category_name]
                    self.accept()


class projectDialog(QDialog, Ui_dlgProject):
    def __init__(self, parent=None):

        super().__init__()

        self.setupUi(self)

        self.lbObservationsState.setText("")
        self.lbSubjectsState.setText("")

        # ethogram tab
        behavior_button_items = [
            "new|Add new behavior",
            "clone|Clone behavior",
            "remove|Remove behavior",
            "remove all|Remove all behaviors",
            "lower|Convert keys to lower case",
        ]
        menu = QMenu()
        menu.triggered.connect(lambda x: self.behavior(action=x.statusTip()))
        self.add_button_menu(behavior_button_items, menu)
        self.pb_behavior.setMenu(menu)

        import_button_items = [
            "boris|from a BORIS project",
            "jwatcher|from a JWatcher project",
            "text|from a text file",
            "clipboard|from the clipboard",
            "repository|from the BORIS repository",
        ]
        menu = QMenu()
        menu.triggered.connect(lambda x: self.import_ethogram(action=x.statusTip()))
        self.add_button_menu(import_button_items, menu)
        self.pb_import.setMenu(menu)

        self.pbBehaviorsCategories.clicked.connect(self.pbBehaviorsCategories_clicked)

        self.pb_exclusion_matrix.clicked.connect(self.exclusion_matrix)

        self.pbExportEthogram.clicked.connect(self.export_ethogram)

        self.twBehaviors.cellChanged[int, int].connect(self.twBehaviors_cellChanged)
        self.twBehaviors.cellDoubleClicked[int, int].connect(self.twBehaviors_cellDoubleClicked)

        # left align table header
        for i in range(self.twBehaviors.columnCount()):
            self.twBehaviors.horizontalHeaderItem(i).setTextAlignment(Qt.AlignLeft)

        # subjects
        self.pbAddSubject.clicked.connect(self.pbAddSubject_clicked)
        self.pbRemoveSubject.clicked.connect(self.pbRemoveSubject_clicked)
        self.pb_remove_all_subjects.clicked.connect(self.remove_all_subjects)

        self.twSubjects.cellChanged[int, int].connect(self.twSubjects_cellChanged)

        self.pb_convert_subjects_key_to_lower.clicked.connect(self.convert_subjects_keys_to_lower_case)

        self.pbImportSubjectsFromProject.clicked.connect(self.pbImportSubjectsFromProject_clicked)
        self.pb_import_subjects_from_clipboard.clicked.connect(
            lambda: project_import.import_subjects_from_clipboard(self)
        )

        # independent variables tab
        self.pbAddVariable.clicked.connect(self.pbAddVariable_clicked)
        self.pbRemoveVariable.clicked.connect(self.pbRemoveVariable_clicked)

        self.leLabel.textChanged.connect(self.leLabel_changed)
        self.leDescription.textChanged.connect(self.leDescription_changed)
        self.lePredefined.textChanged.connect(self.lePredefined_changed)
        self.leSetValues.textChanged.connect(self.leSetValues_changed)
        self.dte_default_date.dateTimeChanged.connect(self.dte_default_date_changed)

        self.twVariables.cellClicked[int, int].connect(self.twVariables_cellClicked)

        self.cbType.currentIndexChanged.connect(self.cbtype_changed)
        self.cbType.activated.connect(self.cbtype_activated)

        self.pbImportVarFromProject.clicked.connect(self.pbImportVarFromProject_clicked)

        self.pbOK.clicked.connect(self.pbOK_clicked)
        self.pbCancel.clicked.connect(self.pbCancel_clicked)

        self.selected_twvariables_row = -1

        self.pbAddBehaviorsCodingMap.clicked.connect(self.add_behaviors_coding_map)
        self.pbRemoveBehaviorsCodingMap.clicked.connect(self.remove_behaviors_coding_map)

        # converters tab
        self.pb_add_converter.clicked.connect(lambda: converters.add_converter(self))
        self.pb_modify_converter.clicked.connect(lambda: converters.modify_converter(self))
        self.pb_save_converter.clicked.connect(lambda: converters.save_converter(self))
        self.pb_cancel_converter.clicked.connect(lambda: converters.cancel_converter(self))
        self.pb_delete_converter.clicked.connect(lambda: converters.delete_converter(self))

        self.pb_load_from_file.clicked.connect(lambda: converters.load_converters_from_file_repo(self, mode="file"))
        self.pb_load_from_repo.clicked.connect(lambda: converters.load_converters_from_file_repo(self, mode="repo"))

        self.pb_code_help.clicked.connect(lambda: converters.pb_code_help_clicked(self))

        self.row_in_modification = -1
        self.flag_modified = False

        for w in [
            self.le_converter_name,
            self.le_converter_description,
            self.pteCode,
            self.pb_save_converter,
            self.pb_cancel_converter,
        ]:
            w.setEnabled(False)

        # disable widget for indep var setting
        for widget in [
            self.leLabel,
            self.le_converter_description,
            self.cbType,
            self.lePredefined,
            self.dte_default_date,
            self.leSetValues,
        ]:
            widget.setEnabled(False)

        self.twBehaviors.horizontalHeader().sortIndicatorChanged.connect(self.sort_twBehaviors)
        self.twSubjects.horizontalHeader().sortIndicatorChanged.connect(self.sort_twSubjects)
        self.twVariables.horizontalHeader().sortIndicatorChanged.connect(self.sort_twVariables)

    def add_button_menu(self, data, menu_obj):
        """
        add menu option from dictionary
        """
        if isinstance(data, dict):
            for k, v in data.items():
                sub_menu = QMenu(k, menu_obj)
                menu_obj.addMenu(sub_menu)
                self.add_button_menu(v, sub_menu)
        elif isinstance(data, list):
            for element in data:
                self.add_button_menu(element, menu_obj)
        else:
            action = menu_obj.addAction(data.split("|")[1])
            # tips are used to discriminate the menu option
            action.setStatusTip(data.split("|")[0])
            action.setIconVisibleInMenu(False)

    def behavior(self, action):
        """
        behavior menu
        """
        if action == "new":
            self.add_behavior()
        if action == "clone":
            self.clone_behavior()
        if action == "remove":
            self.remove_behavior()
        if action == "remove all":
            self.remove_all_behaviors()
        if action == "lower":
            self.convert_behaviors_keys_to_lower_case()

    def import_ethogram(self, action):
        """
        import behaviors
        """
        if action == "boris":
            project_import.import_behaviors_from_project(self)
        if action == "jwatcher":
            project_import.import_from_JWatcher(self)
        if action == "text":
            project_import.import_from_text_file(self)
        if action == "clipboard":
            project_import.import_behaviors_from_clipboard(self)
        if action == "repository":
            project_import.import_behaviors_from_repository(self)

    def sort_twBehaviors(self, index, order):
        """
        order ethogram table
        """
        self.twBehaviors.sortItems(index, order)

    def sort_twSubjects(self, index, order):
        """
        order subjects table
        """
        self.twSubjects.sortItems(index, order)

    def sort_twVariables(self, index, order):
        """
        order variables table
        """
        self.twVariables.sortItems(index, order)

    def convert_behaviors_keys_to_lower_case(self):
        """
        convert behaviors key to lower case to help to migrate to v. 7
        """

        if not self.twBehaviors.rowCount():
            QMessageBox.critical(
                None,
                cfg.programName,
                "The ethogram is empty",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        # check if some keys will be duplicated after conversion
        try:
            all_keys = [
                self.twBehaviors.item(row, cfg.behavioursFields["key"]).text()
                for row in range(self.twBehaviors.rowCount())
            ]
        except Exception:
            pass
        if all_keys == [x.lower() for x in all_keys]:
            QMessageBox.information(self, cfg.programName, "All keys are already lower case")
            return

        if (
            dialog.MessageDialog(cfg.programName, "Confirm the conversion of key to lower case.", [cfg.YES, cfg.CANCEL])
            == cfg.CANCEL
        ):
            return

        if len([x.lower() for x in all_keys]) != len(set([x.lower() for x in all_keys])):
            if (
                dialog.MessageDialog(
                    cfg.programName,
                    "Some keys will be duplicated after conversion. Proceed?",
                    [cfg.YES, cfg.CANCEL],
                )
                == cfg.CANCEL
            ):
                return

        for row in range(self.twBehaviors.rowCount()):
            if self.twBehaviors.item(row, cfg.behavioursFields["key"]).text():
                self.twBehaviors.item(row, cfg.behavioursFields["key"]).setText(
                    self.twBehaviors.item(row, cfg.behavioursFields["key"]).text().lower()
                )

            # convert modifier shortcuts
            if self.twBehaviors.item(row, cfg.behavioursFields["modifiers"]).text():

                modifiers_dict = (
                    eval(self.twBehaviors.item(row, cfg.behavioursFields["modifiers"]).text())
                    if self.twBehaviors.item(row, cfg.behavioursFields["modifiers"]).text()
                    else {}
                )

                for modifier_set in modifiers_dict:
                    try:
                        for idx2, value in enumerate(modifiers_dict[modifier_set]["values"]):
                            if re.findall(r"\((\w+)\)", value):
                                modifiers_dict[modifier_set]["values"][idx2] = (
                                    value.split("(")[0]
                                    + "("
                                    + re.findall(r"\((\w+)\)", value)[0].lower()
                                    + ")"
                                    + value.split(")")[-1]
                                )
                    except Exception:
                        logging.warning("error during conversion of modifier short cut to lower case")

                self.twBehaviors.item(row, cfg.behavioursFields["modifiers"]).setText(str(modifiers_dict))

    def convert_subjects_keys_to_lower_case(self):
        """
        convert subjects key to lower case to help to migrate to v. 7
        """
        # check if some keys will be duplicated after conversion
        try:
            all_keys = [
                self.twSubjects.item(row, cfg.subjectsFields.index("key")).text()
                for row in range(self.twSubjects.rowCount())
            ]
        except Exception:
            pass
        if all_keys == [x.lower() for x in all_keys]:
            QMessageBox.information(self, cfg.programName, "All keys are already lower case")
            return

        if (
            dialog.MessageDialog(cfg.programName, "Confirm the conversion of key to lower case.", [cfg.YES, cfg.CANCEL])
            == cfg.CANCEL
        ):
            return

        if len([x.lower() for x in all_keys]) != len(set([x.lower() for x in all_keys])):
            if (
                dialog.MessageDialog(
                    cfg.programName,
                    "Some keys will be duplicated after conversion. Proceed?",
                    [cfg.YES, cfg.CANCEL],
                )
                == cfg.CANCEL
            ):
                return

        for row in range(self.twSubjects.rowCount()):
            if self.twSubjects.item(row, cfg.subjectsFields.index("key")).text():
                self.twSubjects.item(row, cfg.subjectsFields.index("key")).setText(
                    self.twSubjects.item(row, cfg.subjectsFields.index("key")).text().lower()
                )

    def add_behaviors_coding_map(self):
        """
        Add a behaviors coding map from file
        """

        fn = QFileDialog().getOpenFileName(
            self, "Open a behaviors coding map", "", "Behaviors coding map (*.behav_coding_map);;All files (*)"
        )
        file_name = fn[0] if type(fn) is tuple else fn
        if file_name:
            try:
                bcm = json.loads(open(file_name, "r").read())
            except Exception:
                QMessageBox.critical(self, cfg.programName, f"The file {file_name} is not a behaviors coding map.")
                return

            if "coding_map_type" not in bcm or bcm["coding_map_type"] != "BORIS behaviors coding map":
                QMessageBox.critical(
                    self, cfg.programName, f"The file {file_name} is not a BORIS behaviors coding map."
                )

            if cfg.BEHAVIORS_CODING_MAP not in self.pj:
                self.pj[cfg.BEHAVIORS_CODING_MAP] = []

            bcm_code_not_found = []
            existing_codes = [self.pj[cfg.ETHOGRAM][key]["code"] for key in self.pj[cfg.ETHOGRAM]]
            for code in [bcm["areas"][key]["code"] for key in bcm["areas"]]:
                if code not in existing_codes:
                    bcm_code_not_found.append(code)

            if bcm_code_not_found:
                QMessageBox.warning(
                    self,
                    cfg.programName,
                    ("The following behavior{} are not defined in the ethogram:<br>" "{}").format(
                        "s" if len(bcm_code_not_found) > 1 else "", ",".join(bcm_code_not_found)
                    ),
                )

            self.pj[cfg.BEHAVIORS_CODING_MAP].append(dict(bcm))

            self.twBehavCodingMap.setRowCount(self.twBehavCodingMap.rowCount() + 1)

            self.twBehavCodingMap.setItem(self.twBehavCodingMap.rowCount() - 1, 0, QTableWidgetItem(bcm["name"]))
            codes = ", ".join([bcm["areas"][idx]["code"] for idx in bcm["areas"]])
            self.twBehavCodingMap.setItem(self.twBehavCodingMap.rowCount() - 1, 1, QTableWidgetItem(codes))

    def remove_behaviors_coding_map(self):
        """
        remove the first selected behaviors coding map
        """
        if not self.twBehavCodingMap.selectedIndexes():
            QMessageBox.warning(self, cfg.programName, "Select a behaviors coding map")
        else:
            if (
                dialog.MessageDialog(
                    cfg.programName, "Remove the selected behaviors coding map?", [cfg.YES, cfg.CANCEL]
                )
                == cfg.YES
            ):
                del self.pj[cfg.BEHAVIORS_CODING_MAP][self.twBehavCodingMap.selectedIndexes()[0].row()]
                self.twBehavCodingMap.removeRow(self.twBehavCodingMap.selectedIndexes()[0].row())

    def export_ethogram(self):
        """
        export ethogram in various format
        """
        extended_file_formats = [
            "Tab Separated Values (*.tsv)",
            "Comma Separated Values (*.csv)",
            "Open Document Spreadsheet ODS (*.ods)",
            "Microsoft Excel Spreadsheet XLSX (*.xlsx)",
            "Legacy Microsoft Excel Spreadsheet XLS (*.xls)",
            "HTML (*.html)",
        ]
        file_formats = ["tsv", "csv", "ods", "xlsx", "xls", "html"]

        filediag_func = QFileDialog().getSaveFileName

        fileName, filter_ = filediag_func(self, "Export ethogram", "", ";;".join(extended_file_formats))
        if not fileName:
            return

        outputFormat = file_formats[extended_file_formats.index(filter_)]
        if pathlib.Path(fileName).suffix != "." + outputFormat:
            fileName = str(pathlib.Path(fileName)) + "." + outputFormat

        ethogram_data = tablib.Dataset()
        ethogram_data.title = "Ethogram"
        if self.leProjectName.text():
            ethogram_data.title = f"Ethogram of {self.leProjectName.text()} project"

        ethogram_data.headers = [
            "Behavior code",
            "Behavior type",
            "Description",
            "Key",
            "Behavioral category",
            "Excluded behaviors",
            "modifiers names and values",
            "modifiers (JSON)",
        ]

        for r in range(self.twBehaviors.rowCount()):
            row = []
            for field in ["code", cfg.TYPE, "description", "key", "category", "excluded"]:
                row.append(self.twBehaviors.item(r, cfg.behavioursFields[field]).text())

            # modifiers
            if self.twBehaviors.item(r, cfg.behavioursFields["modifiers"]).text():
                modifiers_dict = eval(self.twBehaviors.item(r, cfg.behavioursFields["modifiers"]).text())
                modifiers_list = []
                for key in modifiers_dict:
                    if modifiers_dict[key]["values"]:
                        values = ", ".join(modifiers_dict[key]["values"])
                        modifiers_list.append(f"{modifiers_dict[key]['name']} ({values})")
                    else:
                        modifiers_list.append(modifiers_dict[key]["name"])

                row.append(", ".join(modifiers_list))
                row.append(json.dumps(modifiers_dict))
            else:
                row.append("")
                row.append("")

            ethogram_data.append(row)

        ok, msg = export_observation.dataset_write(ethogram_data, fileName, outputFormat)
        if not ok:
            QMessageBox.critical(None, cfg.programName, msg, QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton)

    def leLabel_changed(self):

        if self.selected_twvariables_row != -1:
            self.twVariables.item(self.selected_twvariables_row, 0).setText(self.leLabel.text())

    def leDescription_changed(self):

        if self.selected_twvariables_row != -1:
            self.twVariables.item(self.selected_twvariables_row, 1).setText(self.leDescription.text())

    def lePredefined_changed(self):

        if self.selected_twvariables_row != -1:
            self.twVariables.item(self.selected_twvariables_row, 3).setText(self.lePredefined.text())
            if not self.lePredefined.hasFocus():
                r, msg = self.check_indep_var_config()
                if not r:
                    QMessageBox.warning(self, f"{cfg.programName} - Independent variables error", msg)

    def leSetValues_changed(self):

        if self.selected_twvariables_row != -1:
            self.twVariables.item(self.selected_twvariables_row, 4).setText(self.leSetValues.text())

    def dte_default_date_changed(self):

        if self.selected_twvariables_row != -1:
            self.twVariables.item(self.selected_twvariables_row, 3).setText(
                self.dte_default_date.dateTime().toString(Qt.ISODate)
            )

    def pbBehaviorsCategories_clicked(self):
        """
        behavioral categories manager
        """

        bc = BehavioralCategories(self.pj)

        if bc.exec_():
            self.pj[cfg.BEHAVIORAL_CATEGORIES] = []
            for index in range(bc.lw.count()):
                self.pj[cfg.BEHAVIORAL_CATEGORIES].append(bc.lw.item(index).text().strip())

            # check if behavior belong to removed category
            if bc.removed:
                for row in range(self.twBehaviors.rowCount()):
                    if self.twBehaviors.item(row, cfg.behavioursFields["category"]):
                        if self.twBehaviors.item(row, cfg.behavioursFields["category"]).text() == bc.removed:
                            if (
                                dialog.MessageDialog(
                                    cfg.programName,
                                    (
                                        f"The <b>{self.twBehaviors.item(row, cfg.behavioursFields['code']).text()}</b> behavior belongs "
                                        f"to a behavioral category <b>{self.twBehaviors.item(row, cfg.behavioursFields['category']).text()}</b> "
                                        "that is no more in the behavioral categories list.<br><br>"
                                        "Remove the behavior from category?"
                                    ),
                                    [cfg.YES, cfg.CANCEL],
                                )
                                == cfg.YES
                            ):
                                self.twBehaviors.item(row, cfg.behavioursFields["category"]).setText("")
            if bc.renamed:
                for row in range(self.twBehaviors.rowCount()):
                    if self.twBehaviors.item(row, cfg.behavioursFields["category"]):
                        if self.twBehaviors.item(row, cfg.behavioursFields["category"]).text() == bc.renamed[0]:
                            self.twBehaviors.item(row, cfg.behavioursFields["category"]).setText(bc.renamed[1])

    def twBehaviors_cellDoubleClicked(self, row, column):
        """
        manage double-click on ethogram table:
        * behavioral category
        * modifiers
        * exclusion
        * modifiers coding map

        Args:
            row (int): row double-clicked
            column (int): column double-clicked
        """

        # check if double click on excluded column
        if column == cfg.behavioursFields["excluded"]:
            self.pbExclusionMatrix_clicked()

        # check if double click on 'coding map' column
        if column == cfg.behavioursFields["coding map"]:
            if "with coding map" in self.twBehaviors.item(row, cfg.behavioursFields[cfg.TYPE]).text():
                self.behaviorTypeChanged(row)
            else:
                QMessageBox.information(
                    self, cfg.programName, "Change the behavior type on first column to select a coding map"
                )

        # check if double click on category
        if column == cfg.behavioursFields["type"]:
            self.behavior_type_doubleclicked(row)

        # behavioral category
        if column == cfg.behavioursFields["category"]:
            self.category_doubleclicked(row)

        if column == cfg.behavioursFields["modifiers"]:
            # check if behavior has coding map
            if (
                self.twBehaviors.item(row, cfg.behavioursFields["coding map"]) is not None
                and self.twBehaviors.item(row, cfg.behavioursFields["coding map"]).text()
            ):
                QMessageBox.warning(self, cfg.programName, "Use the coding map to set/modify the areas")
            else:
                subjects_list = []
                for subject_row in range(self.twSubjects.rowCount()):
                    key = self.twSubjects.item(subject_row, 0).text() if self.twSubjects.item(subject_row, 0) else ""
                    subjectName = (
                        self.twSubjects.item(subject_row, 1).text().strip()
                        if self.twSubjects.item(subject_row, 1)
                        else ""
                    )
                    subjects_list.append((subjectName, key))

                addModifierWindow = add_modifier.addModifierDialog(
                    self.twBehaviors.item(row, column).text(), subjects=subjects_list
                )
                addModifierWindow.setWindowTitle(f'Set modifiers for "{self.twBehaviors.item(row, 2).text()}" behavior')
                if addModifierWindow.exec_():
                    self.twBehaviors.item(row, column).setText(addModifierWindow.getModifiers())

    def behavior_type_doubleclicked(self, row):
        """
        select type for behavior
        """

        if self.twBehaviors.item(row, cfg.behavioursFields[cfg.TYPE]).text() in cfg.BEHAVIOR_TYPES:
            selected = cfg.BEHAVIOR_TYPES.index(self.twBehaviors.item(row, cfg.behavioursFields[cfg.TYPE]).text())
        else:
            selected = 0

        new_type, ok = QInputDialog.getItem(
            self, "Select a behavior type", "Types of behavior", cfg.BEHAVIOR_TYPES, selected, False
        )

        if ok and new_type:
            self.twBehaviors.item(row, cfg.behavioursFields["type"]).setText(new_type)

            self.behaviorTypeChanged(row)

    def category_doubleclicked(self, row):
        """
        select category for behavior
        """

        categories = ["None"] + self.pj[cfg.BEHAVIORAL_CATEGORIES] if cfg.BEHAVIORAL_CATEGORIES in self.pj else ["None"]

        if self.twBehaviors.item(row, cfg.behavioursFields["category"]).text() in categories:
            selected = categories.index(self.twBehaviors.item(row, cfg.behavioursFields["category"]).text())
        else:
            selected = 0

        category, ok = QInputDialog.getItem(
            self, "Select a behavioral category", "Behavioral categories", categories, selected, False
        )

        if ok and category:
            if category == "None":
                category = ""
            self.twBehaviors.item(row, cfg.behavioursFields["category"]).setText(category)

    def check_variable_default_value(self, txt, varType):
        """
        check if variable default value is compatible with variable type
        """
        # check for numeric type
        if varType == cfg.NUMERIC:
            try:
                if txt:
                    float(txt)
                return True
            except Exception:
                return False

        return True

    def variableTypeChanged(self, row):
        """
        variable type combobox changed
        """

        if self.twVariables.cellWidget(row, cfg.tw_indVarFields.index("type")).currentText() == cfg.SET_OF_VALUES:
            if self.twVariables.item(row, cfg.tw_indVarFields.index("possible values")).text() == "NA":
                self.twVariables.item(row, cfg.tw_indVarFields.index("possible values")).setText(
                    "Double-click to add values"
                )
        else:
            # check if set of values defined
            if self.twVariables.item(row, cfg.tw_indVarFields.index("possible values")).text() not in [
                "NA",
                "Double-click to add values",
            ]:
                if (
                    dialog.MessageDialog(cfg.programName, "Erase the set of values?", [cfg.YES, cfg.CANCEL])
                    == cfg.CANCEL
                ):
                    self.twVariables.cellWidget(row, cfg.tw_indVarFields.index("type")).setCurrentIndex(
                        cfg.SET_OF_VALUES_idx
                    )
                    return
                else:
                    self.twVariables.item(row, cfg.tw_indVarFields.index("possible values")).setText("NA")
            else:
                self.twVariables.item(row, cfg.tw_indVarFields.index("possible values")).setText("NA")

        # check compatibility between variable type and default value
        if not self.check_variable_default_value(
            self.twVariables.item(row, cfg.tw_indVarFields.index("default value")).text(),
            self.twVariables.cellWidget(row, cfg.tw_indVarFields.index("type")).currentIndex(),
        ):
            QMessageBox.warning(
                self,
                cfg.programName + " - Independent variables error",
                (
                    f"The default value ({self.twVariables.item(row, cfg.tw_indVarFields.index('default value')).text()}) "
                    f"of variable <b>{self.twVariables.item(row, cfg.tw_indVarFields.index('label')).text()}</b> "
                    "is not compatible with variable type"
                ),
            )

    def check_indep_var_config(self) -> tuple:
        """
        check if default type is compatible with var type
        """

        existing_var = []
        for r in range(self.twVariables.rowCount()):

            if self.twVariables.item(r, 0).text().strip().upper() in existing_var:
                return (
                    False,
                    f"Row: {r + 1} - The variable label <b>{self.twVariables.item(r, 0).text()}</b> is already in use.",
                )

            # check if same lables
            existing_var.append(self.twVariables.item(r, 0).text().strip().upper())

            # check default value
            if self.twVariables.item(r, 2).text() != cfg.TIMESTAMP and not self.check_variable_default_value(
                self.twVariables.item(r, 3).text(), self.twVariables.item(r, 2).text()
            ):
                return False, (
                    f"Row: {r + 1} - "
                    f"The default value ({self.twVariables.item(r, 3).text()}) is not compatible "
                    f"with the variable type ({self.twVariables.item(r, 2).text()})"
                )

            # check if default value in set of values
            if self.twVariables.item(r, 2).text() == cfg.SET_OF_VALUES and self.twVariables.item(r, 4).text() == "":
                return False, "No values were defined in set"

            if (
                self.twVariables.item(r, 2).text() == cfg.SET_OF_VALUES
                and self.twVariables.item(r, 4).text()
                and self.twVariables.item(r, 3).text()
                and self.twVariables.item(r, 3).text() not in self.twVariables.item(r, 4).text().split(",")
            ):
                return (
                    False,
                    f"The default value ({self.twVariables.item(r, 3).text()}) is not contained in set of values",
                )

        return True, "OK"

    def cbtype_changed(self):

        self.leSetValues.setVisible(self.cbType.currentText() == cfg.SET_OF_VALUES)
        self.label_5.setVisible(self.cbType.currentText() == cfg.SET_OF_VALUES)

        self.dte_default_date.setVisible(self.cbType.currentText() == cfg.TIMESTAMP)
        self.label_9.setVisible(self.cbType.currentText() == cfg.TIMESTAMP)
        self.lePredefined.setVisible(self.cbType.currentText() != cfg.TIMESTAMP)
        self.label_4.setVisible(self.cbType.currentText() != cfg.TIMESTAMP)

    def cbtype_activated(self):

        if self.cbType.currentText() == cfg.TIMESTAMP:
            self.twVariables.item(self.selected_twvariables_row, 3).setText(
                self.dte_default_date.dateTime().toString(Qt.ISODate)
            )
            self.twVariables.item(self.selected_twvariables_row, 4).setText("")
        else:
            self.twVariables.item(self.selected_twvariables_row, 3).setText(self.lePredefined.text())
            self.twVariables.item(self.selected_twvariables_row, 4).setText("")

        # remove spaces after and before comma
        if self.cbType.currentText() == cfg.SET_OF_VALUES:
            self.twVariables.item(self.selected_twvariables_row, 4).setText(
                ",".join([x.strip() for x in self.leSetValues.text().split(",")])
            )

        self.twVariables.item(self.selected_twvariables_row, 2).setText(self.cbType.currentText())

        r, msg = self.check_indep_var_config()

        if not r:
            QMessageBox.warning(self, f"{cfg.programName} - Independent variables error", msg)

    def pbAddVariable_clicked(self):
        """
        add an independent variable
        """

        logging.debug("add an independent variable")
        self.twVariables.setRowCount(self.twVariables.rowCount() + 1)
        self.selected_twvariables_row = self.twVariables.rowCount() - 1

        for idx, field in enumerate(cfg.tw_indVarFields):
            if field == "type":
                item = QTableWidgetItem("numeric")
            else:
                item = QTableWidgetItem("")
            self.twVariables.setItem(self.twVariables.rowCount() - 1, idx, item)

        self.twVariables.setCurrentCell(self.twVariables.rowCount() - 1, 0)

        self.twVariables_cellClicked(self.twVariables.rowCount() - 1, 0)

    def pbRemoveVariable_clicked(self):
        """
        remove the selected independent variable
        """
        logging.debug("remove selected independent variable")

        if not self.twVariables.selectedIndexes():
            QMessageBox.warning(self, cfg.programName, "Select a variable to remove")
        else:
            if dialog.MessageDialog(cfg.programName, "Remove the selected variable?", [cfg.YES, cfg.CANCEL]) == cfg.YES:
                self.twVariables.removeRow(self.twVariables.selectedIndexes()[0].row())

        if self.twVariables.selectedIndexes():
            self.twVariables_cellClicked(self.twVariables.selectedIndexes()[0].row(), 0)
        else:
            self.twVariables_cellClicked(-1, 0)

    def pbImportVarFromProject_clicked(self):
        """
        import independent variables from another project
        """

        project_import.import_indep_variables_from_project(self)

    def pbImportSubjectsFromProject_clicked(self):
        """
        import subjects from another project
        """

        project_import.import_subjects_from_project(self)

    def exclusion_matrix(self):
        """
        activate exclusion matrix window
        """

        if not self.twBehaviors.rowCount():
            QMessageBox.critical(
                None,
                cfg.programName,
                "The ethogram is empty",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        for row in range(self.twBehaviors.rowCount()):
            if not self.twBehaviors.item(row, cfg.behavioursFields["code"]).text():
                QMessageBox.critical(
                    None,
                    cfg.programName,
                    f"A behavior code is empty at row {row + 1}",
                    QMessageBox.Ok | QMessageBox.Default,
                    QMessageBox.NoButton,
                )
                return

        ex = exclusion_matrix.ExclusionMatrix()

        state_behaviors, point_behaviors, allBehaviors, excl, new_excl = [], [], [], {}, {}

        # list of point events
        for r in range(self.twBehaviors.rowCount()):
            if self.twBehaviors.item(r, cfg.behavioursFields[cfg.BEHAVIOR_CODE]):
                if "Point" in self.twBehaviors.item(r, cfg.behavioursFields[cfg.TYPE]).text():
                    point_behaviors.append(self.twBehaviors.item(r, cfg.behavioursFields[cfg.BEHAVIOR_CODE]).text())

        # check if point are present and if user want to include them in exclusion matrix
        include_point_events = cfg.NO
        if point_behaviors:
            include_point_events = dialog.MessageDialog(
                cfg.programName,
                "Do you want to include the point events in the exclusion matrix?",
                [cfg.YES, cfg.NO],
            )

        for r in range(self.twBehaviors.rowCount()):

            if self.twBehaviors.item(r, cfg.behavioursFields[cfg.BEHAVIOR_CODE]):

                if include_point_events == cfg.YES or (
                    include_point_events == cfg.NO
                    and "State" in self.twBehaviors.item(r, cfg.behavioursFields[cfg.TYPE]).text()
                ):
                    allBehaviors.append(self.twBehaviors.item(r, cfg.behavioursFields[cfg.BEHAVIOR_CODE]).text())

                excl[self.twBehaviors.item(r, cfg.behavioursFields[cfg.BEHAVIOR_CODE]).text()] = (
                    self.twBehaviors.item(r, cfg.behavioursFields["excluded"]).text().split(",")
                )
                new_excl[self.twBehaviors.item(r, cfg.behavioursFields[cfg.BEHAVIOR_CODE]).text()] = []

                if "State" in self.twBehaviors.item(r, cfg.behavioursFields[cfg.TYPE]).text():
                    state_behaviors.append(self.twBehaviors.item(r, cfg.behavioursFields[cfg.BEHAVIOR_CODE]).text())

        logging.debug(f"point behaviors: {point_behaviors}")
        logging.debug(f"state behaviors: {state_behaviors}")

        if not state_behaviors:
            QMessageBox.critical(
                None,
                cfg.programName,
                "No state events were defined in ethogram",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        logging.debug(f"exclusion matrix {excl}")

        # first row contain state events
        ex.twExclusions.setColumnCount(len(state_behaviors))
        ex.twExclusions.setHorizontalHeaderLabels(state_behaviors)
        ex.twExclusions.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)

        # first column contains all events: point + state
        ex.twExclusions.setRowCount(len(point_behaviors + state_behaviors))
        for idx, header in enumerate(point_behaviors + state_behaviors):
            item = QTableWidgetItem(header)
            if header in point_behaviors:
                item.setBackground(QColor(0, 200, 200))
            ex.twExclusions.setVerticalHeaderItem(idx, item)
        ex.twExclusions.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        ex.allBehaviors = allBehaviors
        ex.stateBehaviors = state_behaviors
        ex.point_behaviors = point_behaviors

        ex.checkboxes = {}

        for c, c_name in enumerate(state_behaviors):
            flag_left_bottom = False
            for r, r_name in enumerate(point_behaviors + state_behaviors):
                if c_name == r_name:
                    flag_left_bottom = True

                if c_name != r_name:
                    ex.checkboxes[f"{r_name}|{c_name}"] = QCheckBox()
                    ex.checkboxes[f"{r_name}|{c_name}"].setStyleSheet(
                        "text-align: center; margin-left:50%; margin-right:50%;"
                    )

                    if flag_left_bottom:
                        # hide if cell in left-bottom part of table
                        ex.checkboxes[f"{r_name}|{c_name}"].setEnabled(False)

                    # connect function when a CB is clicked
                    ex.checkboxes[f"{r_name}|{c_name}"].clicked.connect(ex.cb_clicked)
                    if c_name in excl[r_name]:
                        ex.checkboxes[f"{r_name}|{c_name}"].setChecked(True)
                    ex.twExclusions.setCellWidget(r, c, ex.checkboxes[f"{r_name}|{c_name}"])

        ex.twExclusions.resizeColumnsToContents()
        # check corresponding checkbox
        ex.cb_clicked()

        if ex.exec_():
            for c, c_name in enumerate(state_behaviors):
                for r, r_name in enumerate(point_behaviors + state_behaviors):
                    if c_name != r_name:
                        if ex.twExclusions.cellWidget(r, c).isChecked():
                            if c_name not in new_excl[r_name]:
                                new_excl[r_name].append(c_name)

            logging.debug(f"new exclusion matrix {new_excl}")

            # update excluded field
            for r in range(self.twBehaviors.rowCount()):
                if include_point_events == cfg.YES or (
                    include_point_events == cfg.NO and "State" in self.twBehaviors.item(r, 0).text()
                ):
                    for e in excl:
                        if e == self.twBehaviors.item(r, cfg.behavioursFields[cfg.BEHAVIOR_CODE]).text():
                            item = QTableWidgetItem(",".join(new_excl[e]))
                            item.setFlags(Qt.ItemIsEnabled)
                            item.setBackground(QColor(230, 230, 230))
                            self.twBehaviors.setItem(r, cfg.behavioursFields["excluded"], item)

    def remove_all_behaviors(self):

        if not self.twBehaviors.rowCount():
            QMessageBox.critical(
                None,
                cfg.programName,
                "The ethogram is empty",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        if dialog.MessageDialog(cfg.programName, "Remove all behaviors?", [cfg.YES, cfg.CANCEL]) != cfg.YES:
            return

        # delete ethogram rows without behavior code
        for r in range(self.twBehaviors.rowCount() - 1, -1, -1):
            if not self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_CODE_FIELD_IDX).text():
                self.twBehaviors.removeRow(r)

        # extract all codes to delete
        codesToDelete = []
        row_mem = {}
        for r in range(self.twBehaviors.rowCount() - 1, -1, -1):
            if self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_CODE_FIELD_IDX).text():
                codesToDelete.append(self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_CODE_FIELD_IDX).text())
                row_mem[self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_CODE_FIELD_IDX).text()] = r

        # extract all codes used in observations
        codesInObs = []
        for obs in self.pj[cfg.OBSERVATIONS]:
            events = self.pj[cfg.OBSERVATIONS][obs][cfg.EVENTS]
            for event in events:
                codesInObs.append(event[cfg.EVENT_BEHAVIOR_FIELD_IDX])

        for codeToDelete in codesToDelete:
            # if code to delete used in obs ask confirmation
            if codeToDelete in codesInObs:
                response = dialog.MessageDialog(
                    cfg.programName,
                    f"The code <b>{codeToDelete}</b> is used in observations!",
                    ["Remove", cfg.CANCEL],
                )
                if response == "Remove":
                    self.twBehaviors.removeRow(row_mem[codeToDelete])
            else:  # remove without asking
                self.twBehaviors.removeRow(row_mem[codeToDelete])

    def twBehaviors_cellChanged(self, row, column):
        """
        check ethogram
        """

        keys, codes = [], []
        self.lbObservationsState.setText("")

        for r in range(self.twBehaviors.rowCount()):

            # check key
            if self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_KEY_FIELD_IDX):
                key = self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_KEY_FIELD_IDX).text()
                # check key length
                if key.upper() not in list(cfg.function_keys.values()) and len(key) > 1:
                    self.lbObservationsState.setText('<font color="red">Key length &gt; 1</font>')
                    return

                keys.append(key)

            # check code
            if self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_CODE_FIELD_IDX):
                if self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_CODE_FIELD_IDX).text() in codes:
                    self.lbObservationsState.setText(f'<font color="red">Code duplicated at line {r + 1} </font>')
                else:
                    if self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_CODE_FIELD_IDX).text():
                        codes.append(self.twBehaviors.item(r, cfg.PROJECT_BEHAVIORS_CODE_FIELD_IDX).text())

    def clone_behavior(self):
        """
        clone the selected configuration
        """

        if not self.twBehaviors.rowCount():
            QMessageBox.critical(
                None,
                cfg.programName,
                "The ethogram is empty",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        if not self.twBehaviors.selectedIndexes():
            QMessageBox.about(self, cfg.programName, "First select a behavior")
        else:
            self.twBehaviors.setRowCount(self.twBehaviors.rowCount() + 1)

            row = self.twBehaviors.selectedIndexes()[0].row()
            for field in cfg.behavioursFields:
                item = QTableWidgetItem(self.twBehaviors.item(row, cfg.behavioursFields[field]))
                self.twBehaviors.setItem(self.twBehaviors.rowCount() - 1, cfg.behavioursFields[field], item)
                if field in [cfg.TYPE, "category", "excluded", "coding map", "modifiers"]:
                    item.setFlags(Qt.ItemIsEnabled)
                    item.setBackground(QColor(230, 230, 230))
        self.twBehaviors.scrollToBottom()

    def remove_behavior(self):
        """
        remove behavior
        """

        if not self.twBehaviors.rowCount():
            QMessageBox.critical(
                None,
                cfg.programName,
                "The ethogram is empty",
                QMessageBox.Ok | QMessageBox.Default,
                QMessageBox.NoButton,
            )
            return

        if not self.twBehaviors.selectedIndexes():
            QMessageBox.warning(self, cfg.programName, "Select a behaviour to be removed")
        else:
            if dialog.MessageDialog(cfg.programName, "Remove the selected behavior?", [cfg.YES, cfg.CANCEL]) == cfg.YES:

                # check if behavior already used in observations
                flag_break = False
                codeToDelete = self.twBehaviors.item(self.twBehaviors.selectedIndexes()[0].row(), 2).text()
                for obs_id in self.pj[cfg.OBSERVATIONS]:
                    if codeToDelete in [
                        event[cfg.EVENT_BEHAVIOR_FIELD_IDX] for event in self.pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS]
                    ]:
                        if (
                            dialog.MessageDialog(
                                cfg.programName, "The code to remove is used in observations!", [cfg.REMOVE, cfg.CANCEL]
                            )
                            == cfg.CANCEL
                        ):
                            return
                        break

                self.twBehaviors.removeRow(self.twBehaviors.selectedIndexes()[0].row())
                self.twBehaviors_cellChanged(0, 0)

    def add_behavior(self):
        """
        add new behavior to ethogram
        """

        # Add behavior to table
        self.twBehaviors.setRowCount(self.twBehaviors.rowCount() + 1)
        for field_type in cfg.behavioursFields:
            item = QTableWidgetItem()
            if field_type == cfg.TYPE:
                item.setText("Point event")
            # no manual editing, gray back ground
            if field_type in [cfg.TYPE, "category", "modifiers", "excluded", "coding map"]:
                item.setFlags(Qt.ItemIsEnabled)
                item.setBackground(QColor(230, 230, 230))
            self.twBehaviors.setItem(self.twBehaviors.rowCount() - 1, cfg.behavioursFields[field_type], item)
        self.twBehaviors.scrollToBottom()

    def behaviorTypeChanged(self, row):
        """
        event type combobox changed
        """

        if "with coding map" in self.twBehaviors.item(row, cfg.behavioursFields[cfg.TYPE]).text():
            # let user select a coding maop
            fn = QFileDialog().getOpenFileName(
                self,
                "Select a coding map for "
                f"{self.twBehaviors.item(row, cfg.behavioursFields['code']).text()} behavior",
                "",
                "BORIS map files (*.boris_map);;All files (*)",
            )
            fileName = fn[0] if type(fn) is tuple else fn

            if fileName:
                try:
                    new_map = json.loads(open(fileName, "r").read())
                except Exception:
                    QMessageBox.critical(self, cfg.programName, "Error reding the file")
                    return
                self.pj[cfg.CODING_MAP][new_map["name"]] = new_map

                # add modifiers from coding map areas
                modifstr = str(
                    {
                        "0": {
                            "name": new_map["name"],
                            "type": cfg.MULTI_SELECTION,
                            "values": list(sorted(new_map["areas"].keys())),
                        }
                    }
                )

                self.twBehaviors.item(row, cfg.behavioursFields["modifiers"]).setText(modifstr)
                self.twBehaviors.item(row, cfg.behavioursFields["coding map"]).setText(new_map["name"])

            else:
                # if coding map already exists do not reset the behavior type if no filename selected
                if not self.twBehaviors.item(row, cfg.behavioursFields["coding map"]).text():
                    QMessageBox.critical(
                        self, cfg.programName, 'No coding map was selected.\nEvent type will be reset to "Point event" '
                    )
                    self.twBehaviors.item(row, cfg.behavioursFields["type"]).setText("Point event")
        else:
            self.twBehaviors.item(row, cfg.behavioursFields["coding map"]).setText("")

    def pbAddSubject_clicked(self):
        """
        add a subject
        """

        self.twSubjects.setRowCount(self.twSubjects.rowCount() + 1)
        for col in range(len(cfg.subjectsFields)):
            item = QTableWidgetItem("")
            self.twSubjects.setItem(self.twSubjects.rowCount() - 1, col, item)
        self.twSubjects.scrollToBottom()

    def pbRemoveSubject_clicked(self):
        """
        remove selected subject from subjects list
        control before if subject used in observations
        """

        if not self.twSubjects.selectedIndexes():
            QMessageBox.warning(self, cfg.programName, "Select a subject to remove")
        else:
            if dialog.MessageDialog(cfg.programName, "Remove the selected subject?", [cfg.YES, cfg.CANCEL]) == cfg.YES:

                flagDel = False
                if self.twSubjects.item(self.twSubjects.selectedIndexes()[0].row(), 1):
                    subjectToDelete = self.twSubjects.item(
                        self.twSubjects.selectedIndexes()[0].row(), 1
                    ).text()  # 1: subject name

                    subjectsInObs = []
                    for obs in self.pj[cfg.OBSERVATIONS]:
                        events = self.pj[cfg.OBSERVATIONS][obs][cfg.EVENTS]
                        for event in events:
                            subjectsInObs.append(event[cfg.EVENT_SUBJECT_FIELD_IDX])
                    if subjectToDelete in subjectsInObs:
                        if (
                            dialog.MessageDialog(
                                cfg.programName,
                                "The subject to remove is used in observations!",
                                [cfg.REMOVE, cfg.CANCEL],
                            )
                            == cfg.REMOVE
                        ):
                            flagDel = True
                    else:
                        # code not used
                        flagDel = True
                else:
                    flagDel = True

                if flagDel:
                    self.twSubjects.removeRow(self.twSubjects.selectedIndexes()[0].row())

                self.twSubjects_cellChanged(0, 0)

    def remove_all_subjects(self):
        """
        remove all subjects.
        Verify if they are used in observations
        """
        if self.twSubjects.rowCount():

            if dialog.MessageDialog(cfg.programName, "Remove all subjects?", [cfg.YES, cfg.CANCEL]) == cfg.YES:

                # delete ethogram rows without behavior code
                for r in range(self.twSubjects.rowCount() - 1, -1, -1):
                    if not self.twSubjects.item(r, 1).text():  # no name
                        self.twSubjects.removeRow(r)

                # extract all subjects names to delete
                namesToDelete = []
                row_mem = {}
                for r in range(self.twSubjects.rowCount() - 1, -1, -1):
                    if self.twSubjects.item(r, 1).text():
                        namesToDelete.append(self.twSubjects.item(r, 1).text())
                        row_mem[self.twSubjects.item(r, 1).text()] = r

                # extract all subjects name used in observations
                namesInObs = []
                for obs in self.pj[cfg.OBSERVATIONS]:
                    events = self.pj[cfg.OBSERVATIONS][obs][cfg.EVENTS]
                    for event in events:
                        namesInObs.append(event[cfg.EVENT_SUBJECT_FIELD_IDX])

                flag_force = False
                for nameToDelete in namesToDelete:
                    # if name to delete used in obs ask confirmation
                    if nameToDelete in namesInObs and not flag_force:
                        response = dialog.MessageDialog(
                            cfg.programName,
                            f"The subject <b>{nameToDelete}</b> is used in observations!",
                            ["Force removing of all subjects", cfg.REMOVE, cfg.CANCEL],
                        )
                        if response == "Force removing of all subjects":
                            flag_force = True
                            self.twSubjects.removeRow(row_mem[nameToDelete])

                        if response == cfg.REMOVE:
                            self.twSubjects.removeRow(row_mem[nameToDelete])
                    else:  # remove without asking
                        self.twSubjects.removeRow(row_mem[nameToDelete])

    def twSubjects_cellChanged(self, row: int, column: int):
        """
        check if subject not unique
        """

        subjects, keys = [], []
        self.lbSubjectsState.setText("")

        for r in range(self.twSubjects.rowCount()):

            # check key
            if self.twSubjects.item(r, 0):

                # check key length
                if (
                    self.twSubjects.item(r, 0).text().upper() not in list(cfg.function_keys.values())
                    and len(self.twSubjects.item(r, 0).text()) > 1
                ):
                    self.lbSubjectsState.setText(
                        (
                            f'<font color="red">Error on key {self.twSubjects.item(r, 0).text()} for subject!</font>'
                            "The key is too long (keys must be of one character"
                            " except for function keys _F1, F2..._)"
                        )
                    )
                    return

                if self.twSubjects.item(r, 0).text() in keys:
                    self.lbSubjectsState.setText(f'<font color="red">Key duplicated at row # {r + 1}</font>')
                else:
                    if self.twSubjects.item(r, 0).text():
                        keys.append(self.twSubjects.item(r, 0).text())

            # check subject
            if self.twSubjects.item(r, 1):
                if self.twSubjects.item(r, 1).text() in subjects:
                    self.lbSubjectsState.setText(f'<font color="red">Subject duplicated at row # {r + 1}</font>')
                else:
                    if self.twSubjects.item(r, 1).text():
                        subjects.append(self.twSubjects.item(r, 1).text())

    def twVariables_cellClicked(self, row, column):
        """
        check if variable default values are compatible with variable type
        """

        self.selected_twvariables_row = row
        logging.debug(f"selected row: {self.selected_twvariables_row}")

        if self.selected_twvariables_row == -1:
            for widget in [
                self.leLabel,
                self.leDescription,
                self.cbType,
                self.lePredefined,
                self.dte_default_date,
                self.leSetValues,
            ]:
                widget.setEnabled(False)
                self.leLabel.setText("")
                self.leDescription.setText("")
                self.lePredefined.setText("")
                self.leSetValues.setText("")

                self.cbType.clear()
            return

        # enable widget for indep var setting
        for widget in [
            self.leLabel,
            self.leDescription,
            self.cbType,
            self.lePredefined,
            self.dte_default_date,
            self.leSetValues,
        ]:
            widget.setEnabled(True)

        self.leLabel.setText(self.twVariables.item(row, 0).text())
        self.leDescription.setText(self.twVariables.item(row, 1).text())
        self.lePredefined.setText(self.twVariables.item(row, 3).text())
        self.leSetValues.setText(self.twVariables.item(row, 4).text())

        self.cbType.clear()
        self.cbType.addItems(cfg.AVAILABLE_INDEP_VAR_TYPES)
        self.cbType.setCurrentIndex(cfg.NUMERIC_idx)

        self.cbType.setCurrentIndex(cfg.AVAILABLE_INDEP_VAR_TYPES.index(self.twVariables.item(row, 2).text()))

    def pbCancel_clicked(self):
        if self.flag_modified:
            if (
                dialog.MessageDialog(
                    "BORIS", "The converters were modified. Are you sure to cancel?", [cfg.CANCEL, cfg.OK]
                )
                == cfg.OK
            ):
                self.reject()
        else:
            self.reject()

    def pbOK_clicked(self):
        """
        verify project configuration
        """

        if self.lbObservationsState.text():
            QMessageBox.warning(self, cfg.programName, self.lbObservationsState.text())
            return

        if self.lbSubjectsState.text():
            QMessageBox.warning(self, cfg.programName, self.lbSubjectsState.text())
            return

        self.pj["project_name"] = self.leProjectName.text().strip()
        self.pj["project_date"] = self.dteDate.dateTime().toString(Qt.ISODate)
        self.pj["project_description"] = self.teDescription.toPlainText()

        # time format
        if self.rbSeconds.isChecked():
            self.pj["time_format"] = cfg.S
        if self.rbHMS.isChecked():
            self.pj["time_format"] = cfg.HHMMSS

        # store subjects
        self.subjects_conf = {}

        # check for leading/trailing spaces in subjects names
        subjects_name_with_leading_trailing_spaces = ""
        for row in range(self.twSubjects.rowCount()):
            if self.twSubjects.item(row, 1):
                if self.twSubjects.item(row, 1).text() != self.twSubjects.item(row, 1).text().strip():
                    subjects_name_with_leading_trailing_spaces += f'"{self.twSubjects.item(row, 1).text()}" '

        remove_leading_trailing_spaces = cfg.NO
        if subjects_name_with_leading_trailing_spaces:

            remove_leading_trailing_spaces = dialog.MessageDialog(
                cfg.programName,
                (
                    "Attention! Some leading and/or trailing spaces are present in the following <b>subject name(s)</b>:<br>"
                    f"<b>{subjects_name_with_leading_trailing_spaces}</b><br><br>"
                    "Do you want to remove the leading and trailing spaces?<br><br>"
                    '<font color="red"><b>Be careful with this option'
                    " if you have already done observations!</b></font>"
                ),
                [cfg.YES, cfg.NO],
            )

        # check subjects
        for row in range(self.twSubjects.rowCount()):
            # check key
            if self.twSubjects.item(row, 0):
                key = self.twSubjects.item(row, 0).text()
            else:
                key = ""

            # check subject name
            if self.twSubjects.item(row, 1):
                if remove_leading_trailing_spaces == cfg.YES:
                    subjectName = self.twSubjects.item(row, 1).text().strip()
                else:
                    subjectName = self.twSubjects.item(row, 1).text()

                # check if subject name is empty
                if subjectName == "":
                    QMessageBox.warning(
                        self, cfg.programName, f"The subject name can not be empty (check row #{row + 1})."
                    )
                    return

                if "|" in subjectName:
                    QMessageBox.warning(
                        self,
                        cfg.programName,
                        f"The pipe (|) character is not allowed in subject name <b>{subjectName}</b>",
                    )
                    return
            else:
                QMessageBox.warning(
                    self, cfg.programName, f"Missing subject name in subjects configuration at row #{row + 1}"
                )
                return

            # description
            subjectDescription = ""
            if self.twSubjects.item(row, 2):
                subjectDescription = self.twSubjects.item(row, 2).text().strip()

            self.subjects_conf[str(len(self.subjects_conf))] = {
                "key": key,
                "name": subjectName,
                "description": subjectDescription,
            }

        self.pj[cfg.SUBJECTS] = dict(self.subjects_conf)

        # store behaviors
        missing_data = []
        self.obs = {}

        # Ethogram
        # coding maps in ethogram

        # check for leading/trailing space in behaviors and modifiers
        code_with_leading_trailing_spaces, modifiers_with_leading_trailing_spaces = [], []
        for r in range(self.twBehaviors.rowCount()):

            if (
                self.twBehaviors.item(r, cfg.behavioursFields["code"]).text()
                != self.twBehaviors.item(r, cfg.behavioursFields["code"]).text().strip()
            ):
                code_with_leading_trailing_spaces.append(self.twBehaviors.item(r, cfg.behavioursFields["code"]).text())

            if self.twBehaviors.item(r, cfg.behavioursFields["modifiers"]).text():
                try:
                    modifiers_dict = eval(self.twBehaviors.item(r, cfg.behavioursFields["modifiers"]).text())
                    for k in modifiers_dict:
                        for value in modifiers_dict[k]["values"]:
                            modif_code = value.split(" (")[0]
                            if modif_code.strip() != modif_code:
                                modifiers_with_leading_trailing_spaces.append(modif_code)
                except Exception:
                    logging.critical("error checking leading/trailing spaces in modifiers")

        remove_leading_trailing_spaces = cfg.NO
        if code_with_leading_trailing_spaces:
            remove_leading_trailing_spaces = dialog.MessageDialog(
                cfg.programName,
                (
                    "<b>Warning!</b> Some leading and/or trailing spaces are present"
                    " in the following behaviors code(s):<br>"
                    f"<b>{'<br>'.join([x.replace(' ', '&#9608;') for x in code_with_leading_trailing_spaces])}</b><br><br>"
                    "Do you want to remove the leading and trailing spaces from behaviors?<br><br>"
                    """<font color="red"><b>Be careful with this option"""
                    """ if you have already done observations!</b></font>"""
                ),
                [cfg.YES, cfg.NO, cfg.CANCEL],
            )
        if remove_leading_trailing_spaces == cfg.CANCEL:
            return

        remove_leading_trailing_spaces_in_modifiers = cfg.NO
        if modifiers_with_leading_trailing_spaces:
            remove_leading_trailing_spaces_in_modifiers = dialog.MessageDialog(
                cfg.programName,
                (
                    "<b>Warning!</b> Some leading and/or trailing spaces are present"
                    " in the following modifier(s):<br>"
                    f"<b>{'<br>'.join([x.replace(' ', '&#9608;') for x in set(modifiers_with_leading_trailing_spaces)])}</b><br><br>"
                    "Do you want to remove the leading and trailing spaces from modifiers?<br><br>"
                    """<font color="red"><b>Be careful with this option"""
                    """ if you have already done observations!</b></font>"""
                ),
                [cfg.YES, cfg.NO, cfg.CANCEL],
            )
        if remove_leading_trailing_spaces_in_modifiers == cfg.CANCEL:
            return

        codingMapsList = []
        for r in range(self.twBehaviors.rowCount()):
            row = {}
            for field in cfg.behavioursFields:
                if self.twBehaviors.item(r, cfg.behavioursFields[field]):

                    # check for | char in code
                    if field == "code" and "|" in self.twBehaviors.item(r, cfg.behavioursFields[field]).text():
                        QMessageBox.warning(
                            self,
                            cfg.programName,
                            (
                                "The pipe (|) character is not allowed in code "
                                f"<b>{self.twBehaviors.item(r, cfg.behavioursFields[field]).text()}</b> !"
                            ),
                        )
                        return

                    if remove_leading_trailing_spaces == cfg.YES:
                        row[field] = self.twBehaviors.item(r, cfg.behavioursFields[field]).text().strip()
                    else:
                        row[field] = self.twBehaviors.item(r, cfg.behavioursFields[field]).text()

                    if field == "modifiers" and row["modifiers"]:

                        if remove_leading_trailing_spaces_in_modifiers == cfg.YES:
                            try:
                                modifiers_dict = eval(row["modifiers"])
                                for k in modifiers_dict:
                                    for idx, value in enumerate(modifiers_dict[k]["values"]):
                                        modif_code = value.split(" (")[0]

                                        modifiers_dict[k]["values"][idx] = modifiers_dict[k]["values"][idx].replace(
                                            modif_code, modif_code.strip()
                                        )

                                row["modifiers"] = dict(modifiers_dict)
                            except Exception:

                                logging.critical("Error removing leading/trailing spaces in modifiers")

                                QMessageBox.critical(
                                    self, cfg.programName, "Error removing leading/trailing spaces in modifiers"
                                )

                        else:
                            row["modifiers"] = eval(row["modifiers"])
                else:
                    row[field] = ""

            if (row["type"]) and (row["code"]):
                self.obs[str(len(self.obs))] = row
            else:
                missing_data.append(str(r + 1))

            if self.twBehaviors.item(r, cfg.behavioursFields["coding map"]).text():
                codingMapsList.append(self.twBehaviors.item(r, cfg.behavioursFields["coding map"]).text())

        # remove coding map from project if not in ethogram
        cmToDelete = []
        for cm in self.pj[cfg.CODING_MAP]:
            if cm not in codingMapsList:
                cmToDelete.append(cm)

        for cm in cmToDelete:
            del self.pj[cfg.CODING_MAP][cm]

        if missing_data:
            QMessageBox.warning(self, cfg.programName, f"Missing data in ethogram at row {','.join(missing_data)} !")
            return

        # check if behavior belong to category that is not in categories list
        behavior_category = []
        for idx in self.obs:
            if cfg.BEHAVIOR_CATEGORY in self.obs[idx]:
                if self.obs[idx][cfg.BEHAVIOR_CATEGORY]:
                    if self.obs[idx][cfg.BEHAVIOR_CATEGORY] not in self.pj[cfg.BEHAVIORAL_CATEGORIES]:
                        behavior_category.append(
                            (self.obs[idx][cfg.BEHAVIOR_CODE], self.obs[idx][cfg.BEHAVIOR_CATEGORY])
                        )
        if behavior_category:

            response = dialog.MessageDialog(
                f"{cfg.programName} - Behavioral categories",
                (
                    "The behavioral categorie(s) "
                    f"{', '.join(set(['<b>' + x[1] + '</b>' + ' (used with <b>' + x[0] + '</b>)' for x in behavior_category]))} "
                    "are no more defined in behavioral categories list"
                ),
                ["Add behavioral category/ies", "Ignore", cfg.CANCEL],
            )
            if response == "Add behavioral category/ies":
                [self.pj[cfg.BEHAVIORAL_CATEGORIES].append(x1) for x1 in set(x[1] for x in behavior_category)]
            if response == cfg.CANCEL:
                return

        # delete coding maps loaded in pj and not cited in ethogram
        self.pj[cfg.ETHOGRAM] = dict(self.obs)

        # independent variables
        r, msg = self.check_indep_var_config()
        if not r:
            QMessageBox.warning(self, cfg.programName + " - Independent variables error", msg)
            return

        self.indVar = {}
        for r in range(self.twVariables.rowCount()):
            row = {}
            for idx, field in enumerate(cfg.tw_indVarFields):
                if self.twVariables.item(r, idx):
                    # check if label is empty
                    if field == "label" and self.twVariables.item(r, idx).text() == "":
                        QMessageBox.warning(
                            self,
                            cfg.programName,
                            f"The label of an indipendent variable can not be empty (check row #{r + 1}).",
                        )
                        return
                    row[field] = self.twVariables.item(r, idx).text().strip()
                else:
                    row[field] = ""

            self.indVar[str(len(self.indVar))] = row

        self.pj[cfg.INDEPENDENT_VARIABLES] = dict(self.indVar)

        # converters
        converters = {}
        for row in range(self.tw_converters.rowCount()):
            converters[self.tw_converters.item(row, 0).text()] = {
                "name": self.tw_converters.item(row, 0).text(),
                "description": self.tw_converters.item(row, 1).text(),
                "code": self.tw_converters.item(row, 2).text().replace("@", "\n"),
            }
        self.pj[cfg.CONVERTERS] = dict(converters)

        self.accept()
