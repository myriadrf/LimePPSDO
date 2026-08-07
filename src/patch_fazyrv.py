import os
import re
import sys

SIGNATURE = "/* PATCHED BY LIMESDR_GW */"

def patch_file(filepath):
    try:
        with open(filepath, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False

    if SIGNATURE in content:
        return False

    filename = os.path.basename(filepath)
    modified = False
    
    # 1. Wrap module-level if-statements that are likely conditional generates
    # in fazyrv_top.sv (known issue with Quartus)
    if filename == "fazyrv_top.sv":
        # Look for the parameter check if statement at the end of the file
        # and other potential module-level if-statements.
        # We target the one specifically mentioned in the error.
        param_check_re = r'(\nif\s*\(!?\(?CHUNKSIZE_OK.*?\)\s*begin.*?end)'
        if re.search(param_check_re, content, re.DOTALL):
            content = re.sub(param_check_re, r'\ngenerate\1\nendgenerate', content, flags=re.DOTALL)
            modified = True

        # Add initial to $fatal/$error if they are at the start of a line without it
        # (excluding those that already have it)
        content, n = re.subn(r'^(\s*)(?!(?:initial\s+))(\$(?:fatal|error|warning|info))', r'\1initial \2', content, flags=re.MULTILINE)
        if n > 0:
            modified = True

    # 2. Name unnamed blocks (for, if, else) inside generate blocks
    # Quartus requires names for these blocks.
    block_count = 0
    def name_blocks(gen_match):
        nonlocal block_count, modified
        gen_content = gen_match.group(0)
        
        def replace_block(match):
            nonlocal block_count, modified
            stmt = match.group(1)
            
            # Special case for fazyrv_rf_lut.sv to keep debug compatibility
            if filename == "fazyrv_rf_lut.sv" and "for" in stmt and "i<32" in stmt:
                name = "regs_a"
            else:
                name = f"g_loop_{block_count}"
            
            block_count += 1
            modified = True
            return f"{stmt}begin : {name}"

        # Match 'for' or 'if' followed by 'begin' without ':'
        # Use .*? to handle potential nested parentheses in if/for conditions
        new_gen_content = re.sub(r'((?:for|if)\s*\(.*?\)\s*)begin(?!\s*:)', replace_block, gen_content, flags=re.DOTALL)
        # Match 'else' followed by 'begin' without ':' (and not 'else if')
        new_gen_content = re.sub(r'(else\s+)begin(?!\s*:)', replace_block, new_gen_content, flags=re.DOTALL)
        return new_gen_content

    new_content = re.sub(r'generate.*?endgenerate', name_blocks, content, flags=re.DOTALL)
    
    if modified:
        new_content = f"{SIGNATURE}\n" + new_content
        try:
            with open(filepath, 'w') as f:
                f.write(new_content)
            return True
        except Exception as e:
            print(f"Error writing {filepath}: {e}")
            return False
    
    return False

def patch_fazyrv_sources():
    # Find the FazyRV/rtl directory relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    rtl_dir = os.path.join(current_dir, "FazyRV/rtl")
    
    if not os.path.exists(rtl_dir):
        # Try relative to CWD if not found
        rtl_dir = os.path.abspath("gateware/LimePPSDO/src/FazyRV/rtl")
        if not os.path.exists(rtl_dir):
             print(f"Directory {rtl_dir} not found.")
             return

    patched_files = []
    for root, dirs, files in os.walk(rtl_dir):
        for file in files:
            if file.endswith(".sv") or file.endswith(".v"):
                if patch_file(os.path.join(root, file)):
                    patched_files.append(file)
    
    if patched_files:
        print(f"Patched FazyRV sources: {', '.join(patched_files)}")
    else:
        print("No FazyRV sources needed patching.")

if __name__ == "__main__":
    patch_fazyrv_sources()
