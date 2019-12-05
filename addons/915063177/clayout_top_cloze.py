# -*- coding: utf-8 -*-
# pylint: disable=unsubscriptable-object,unused-import
from PyQt5 import QtCore, QtGui, QtWidgets

from anki.lang import _

# Form implementation generated from reading ui file 'designer/clayout_top_cloze.ui'
#
# Created by: PyQt5 UI code generator 5.12.1
#
# WARNING! All changes made in this file will be lost!



class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(400, 162)
        self.verticalLayout = QtWidgets.QVBoxLayout(Form)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(3)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setSpacing(12)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtWidgets.QLabel(Form)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.clozeNumber = QtWidgets.QSpinBox(Form)
        self.clozeNumber.setMinimum(1)
        self.clozeNumber.setMaximum(999999)
        self.clozeNumber.setObjectName("clozeNumber")
        self.horizontalLayout.addWidget(self.clozeNumber)
        spacerItem = QtWidgets.QSpacerItem(1, 20, QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.changesLabel = QtWidgets.QLabel(Form)
        self.changesLabel.setText("")
        self.changesLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.changesLabel.setObjectName("changesLabel")
        self.verticalLayout.addWidget(self.changesLabel)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_("Form"))
        self.label.setText(_("Card Number:"))
