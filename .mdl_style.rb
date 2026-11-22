# Style for mdl (markdownlint), used by ./lint.

all

# Documentation lines are at most 72 columns, long table rows and
# commands are accepted.
rule 'MD013', :line_length => 72, :ignore_code_blocks => true, :tables => false

# A command example does not need to show the output.
exclude_rule 'MD014'

# The same header is fine under different parents, for example
# "Commands" in README.md. The allow_different_nesting parameter does
# not help, with it mdl 0.13 complains about "Requirements" which is
# there on two levels.
exclude_rule 'MD024'

# Code blocks are indented, not fenced.
rule 'MD046', :style => :indented
