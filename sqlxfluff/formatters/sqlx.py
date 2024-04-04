import sqlfluff
from sqlfluff.core import FluffConfig

from .base import format_config, format_template
from .indent import replace_with_indentation


def format_sqlx(deconstructed_file: dict, config: FluffConfig):
    """Formats Dataform SQLX files using SQLFluff"""
    # run fix on modified text
    bq_fix_result = sqlfluff.fix(deconstructed_file["main"], config=config).rstrip(
        ";\n"
    )
    pre_operations_fix, post_operations_fix = None, None
    if deconstructed_file["pre_operations"]:
        pre_operations_fix = sqlfluff.fix(deconstructed_file["pre_operations"], config=config).rstrip(
            ";\n"
        )
    if deconstructed_file["post_operations"]:
        post_operations_fix = sqlfluff.fix(deconstructed_file["post_operations"], config=config).rstrip(
            ";\n"
        )
    # place the templates back into the SQLX
    for mask, template in deconstructed_file["templates"].items():
        formatted_template = format_template(template)
        bq_fix_result = replace_with_indentation(
            bq_fix_result, mask, formatted_template
        )

    # recombine the config block and the fixed SQL
    formatted_config_block = format_config(deconstructed_file["config"])
    js_block = deconstructed_file["js"]
    formatted_file = f"{formatted_config_block}\n\n"
    if js_block:
        formatted_file += f"{js_block}\n\n"
    if pre_operations_fix:
        formatted_file += f"{pre_operations_fix}\n\n"
    if post_operations_fix:
        formatted_file += f"{post_operations_fix}\n\n"
    formatted_file += f"{bq_fix_result}\n"
    
    return formatted_file
