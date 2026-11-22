"""prov-skills: agent skills for projects that use prov. Imports prov; prov never imports this package.

One directory per skill, each holding a SKILL.md; adding one touches nothing else.

plot/      the plot skill and its code: house style, save_figure, to_journal (`from prov_skills import plot`)
journal/   the journal skill
cli        `prov-skills install <project>`: links every skill into <project>/.claude/skills/
"""
