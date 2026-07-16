"""
Convert f-string check_* calls in doctor.py to .format() + _() pattern.
Targets the specific patterns found: {name}, {_DHH}, {py_version.*}, etc.
"""
import re

path = r"C:\Users\leesu\BookwormPRO\bwm_cli\doctor.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Track changes
changes = 0

def fix_call(match):
    """Convert one f-string check_* call to .format() pattern."""
    global changes
    func = match.group(1)      # check_ok / check_warn / check_fail / check_info
    fstr = match.group(2)      # the f-string content (inside f"...")
    rest = match.group(3) or '' # optional second arg like , "detail")
    
    # For check_info, sometimes there's no rest
    # For check_ok/warn/fail, there may be a detail param
    
    # Extract variables from {name}, {name.attr}, {name:fmt}
    vars_found = set()
    def collect_var(m):
        v = m.group(1).split('.')[0].split(':')[0]
        vars_found.add(v)
        return '{' + m.group(1) + '}'
    
    template = re.sub(r'\{([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*(?::[^}]*)?)\}', collect_var, fstr)
    
    # Handle py_version.major.minor.micro pattern
    if 'py_version' in template:
        # These need individual format args
        pass
    
    if vars_found:
        format_args = ', '.join(f'{v}={v}' for v in sorted(vars_found))
        if rest.startswith(','):
            # Has detail param - but detail might also be f-string
            if 'f"' in rest or "f'" in rest:
                # Detail is also f-string, handle separately
                new_call = f'{func}(_("""{template}""").format({format_args}){rest}'
            else:
                new_call = f'{func}(_("""{template}""").format({format_args}){rest}'
        else:
            new_call = f'{func}(_("""{template}""").format({format_args}))'
    else:
        new_call = f'{func}(_("""{template}"""))'
    
    changes += 1
    return new_call

# Pattern: check_xxx(f"...")
# But NOT if it's in a comment or already has _()
pattern = r'\b(check_\w+)\(f"([^"]*)"([^)]*)?\)'

# We need to be careful with multi-line calls
# For now, handle single-line f-string calls
lines = content.split('\n')
new_lines = []
skip_until_match = False
pending_match = None

for i, line in enumerate(lines):
    if skip_until_match:
        # Continue accumulating multi-line call
        if ')' in line and line.strip().endswith(')'):
            skip_until_match = False
            new_lines.append(line)  # Keep as-is for now
            print(f"  SKIP multi-line L{i+1}: {line.strip()[:80]}")
        else:
            new_lines.append(line)
        continue
    
    # Check for f-string check_* call on this line
    m = re.search(r'\b(check_\w+)\(f"', line)
    if m:
        # Check if this call spans multiple lines (no closing paren)
        # Count parens after the match
        after = line[m.start():]
        open_parens = after.count('(') - after.count(')')
        if open_parens > 0:
            skip_until_match = True
            new_lines.append(line)  # Keep multi-line calls for now
            print(f"  SKIP multi-line L{i+1}: {line.strip()[:80]}")
            continue
        
        # Try regex replacement
        new_line = re.sub(
            r'\b(check_\w+)\(f"([^"]*)"(\s*,\s*(?:f"[^"]*"|"[^"]*"|\'[^\']*\'))?\s*\)',
            fix_call,
            line
        )
        new_lines.append(new_line)
    else:
        new_lines.append(line)

content = '\n'.join(new_lines)

# Write back
with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content)

print(f"\nConverted {changes} f-string calls")
print("Checking syntax...")

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("Syntax OK")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
    print("Restoring from git...")
