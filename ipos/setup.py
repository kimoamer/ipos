import frappe
import os
import click
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    create_custom_fields(get_custom_fields())
	


def before_uninstall():
    delete_custom_fields(get_custom_fields())


def get_custom_fields():
    """ Adding Custom fields to masters of ERPNEXT to fully integrate"""
    return {
            "POS Profile": [
                {
                    "fieldname": "apply_zero_payment",
                    "fieldtype": "Check",
                    "label": "Apply Zero Payment",
                    "no_copy": 1,
                    "insert_after": "allow_discount_change"
                }
            ],
        }