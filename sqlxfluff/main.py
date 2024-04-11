import argparse
import json
from sys import exit  # pylint: disable=redefined-builtin

import click
import sqlfluff
from sqlfluff.core import FluffConfig
from termcolor import cprint

from .constants import EXIT_FAIL, EXIT_SUCCESS
from .formatters.javascript import validate_prettier_installation
from .formatters.sqlx import format_sqlx
from .linting import parse_sql, print_lint_result, sqlfluff_lint
from .parsing import parse_sqlx


def main():
    """Main entrypoint for the package."""

    validate_prettier_installation()

    parser = argparse.ArgumentParser(
        description="A script that formats and lints Dataform SQLX files."
    )
    parser.add_argument("function", help="Function to execute", choices=["fix", "lint"])
    parser.add_argument(
        "-f",
        "--format",
        help="Output format for linter",
        default="human",
        choices=["human", "json", "github_annotation_native"],
    )
    parser.add_argument(
        "-c", "--config-path", help="Path to the configuration file", default=None
    )
    dialects = [d.name for d in sqlfluff.core.dialect_readout()]
    parser.add_argument(
        "-d", "--dialect", help="SQL dialect to use", choices=dialects, default=None
    )
    parser.add_argument(
        "files", metavar="FILE", type=str, nargs="+", help="File paths to process"
    )
    opts = parser.parse_args()
    function = opts.function
    fmt = opts.format

    if function == "lint":
        output = []
        for filename in opts.files:
            config = FluffConfig.from_path(
                filename if opts.config_path is None else opts.config_path
            )
            config.set_value(
                ["rules", "convention.terminator", "require_final_semicolon"], False
            )
            if opts.dialect is not None:
                config.set_value(["dialect"], opts.dialect)

            with open(filename, "r", encoding="utf-8") as f:
                raw_file_contents = f.read()
            parsed_file_contents = parse_sqlx(raw_file_contents)
            if fmt == "human":
                cprint(filename, attrs=["bold"], end=" ")

            parsing_violations = parse_sql(parsed_file_contents["main"], config)
            if parsing_violations is not None:
                cprint(parsing_violations, "red")

            lint_result = sqlfluff_lint(sql=parsed_file_contents["main"], config=config)
            violations = lint_result[0]["violations"]
            if not violations:
                if fmt == "human":
                    cprint("PASS", color="green")
            else:
                if opts.format == "human":
                    cprint("FAIL", color="red")
                    for result in violations:
                        print_lint_result(result)

                output.append({"filepath": filename, "violations": violations})
        if len(output) > 0:
            file_output = None
            if fmt == "json":
                file_output = json.dumps(output)
            elif fmt == "github_annotation_native":
                annotation_level = "error"
                github_result_native = []
                for record in output:
                    filepath = record["filepath"]
                    for violation in record["violations"]:
                        # NOTE: The output format is designed for GitHub action:
                        # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-a-notice-message

                        # The annotation_level is configurable, but will only apply
                        # to any SQLFluff rules which have not been downgraded
                        # to warnings using the `warnings` config value. Any which have
                        # been set to warn rather than fail will always be given the
                        # `notice` annotation level in the serialised result.
                        # line = "::notice " if violation["warning"] else f"::{annotation_level} "
                        line = f"::{annotation_level} "

                        line += "title=SQLXFluff,"
                        line += f"file={filepath},"
                        line += f"line={violation['line_no']},"
                        line += f"col={violation['line_pos']}"
                        if "end_line_no" in violation:
                            line += f",endLine={violation['end_line_no']}"
                        if "end_line_pos" in violation:
                            line += f",endColumn={violation['end_line_pos']}"
                        line += "::"
                        line += f"{violation['code']}: {violation['description']}"
                        if violation["name"]:
                            line += f" [{violation['name']}]"

                        github_result_native.append(line)
                file_output = "\n".join(github_result_native)
            else:
                file_output = None
            if file_output:
                click.echo(file_output)
            exit(EXIT_FAIL)
        exit(EXIT_SUCCESS)

    if function == "fix":
        fail = False
        for filename in opts.files:
            config = FluffConfig.from_path(
                filename if opts.config_path is None else opts.config_path
            )
            config.set_value(
                ["rules", "convention.terminator", "require_final_semicolon"], False
            )
            if opts.dialect is not None:
                config.set_value(["dialect"], opts.dialect)

            with open(filename, "r", encoding="utf-8") as f:
                raw_file_contents = f.read()
            parsed_file_contents = parse_sqlx(raw_file_contents)

            cprint(filename, attrs=["bold"], end=" ")

            parsing_violations = parse_sql(parsed_file_contents["main"], config)
            if parsing_violations is not None:
                cprint(parsing_violations, "red")

            formatted_file_contents = format_sqlx(parsed_file_contents, config)
            formatted_file_contents_again = format_sqlx(
                parse_sqlx(formatted_file_contents), config
            )
            if formatted_file_contents != formatted_file_contents_again:
                cprint("Formatter unable to determine final formatted form.", "red")
                fail = True

            with open(filename, "w", encoding="utf-8") as f:
                f.write(formatted_file_contents)
        if fail:
            exit(EXIT_FAIL)
        print()


if __name__ == "__main__":
    main()
