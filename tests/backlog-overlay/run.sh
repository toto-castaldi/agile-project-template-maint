#!/bin/sh
# Runs the tests of the Claude Code backlog pane against the template's plugin.
# `claude plugin test` reads *.test.tsx from the plugin folder, so both go to a temporary copy.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
plugin="$here/../../../agile-project-template/.agents/skills/backlog-overlay"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp -R "$plugin/." "$work/"
mkdir -p "$work/tests"
cp "$here/register.test.tsx" "$work/tests/"
claude plugin test "$work"
