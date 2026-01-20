from django import template

register = template.Library()

@register.filter
def split(value, delimiter):
    """Split a string by a delimiter and return a list"""
    if not value:
        return []
    return value.split(delimiter)

@register.filter
def highlight_funding(text):
    """Highlight lines containing $ symbols in funding text"""
    if not text:
        return text

    lines = text.split('\n')
    highlighted_lines = []

    for line in lines:
        if '$' in line.strip():
            highlighted_lines.append(f'<span style="font-weight: 600; color: #10B981;">{line}</span>')
        else:
            highlighted_lines.append(line)

    return '\n'.join(highlighted_lines)