import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
import re
import zipfile
import logging
import argparse
from typing import Dict, List, Tuple

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SCRIPT_DIR = Path(__file__).parent
PROXIES_DIR = SCRIPT_DIR / 'proxies'
OUTPUT_DIR = SCRIPT_DIR / 'output'
OUTPUT_PROXIES_DIR = OUTPUT_DIR / 'proxies'
UNATTACHED_POLICIES_REPORT_PATH = OUTPUT_DIR / 'unattached_policies_summary.txt'
SIZE_SUMMARY_REPORT_PATH = OUTPUT_DIR / 'refactor_summary_report.md'
SEQUENTIAL_JS_REPORT_PATH = OUTPUT_DIR / 'sequential_js_steps_report.txt'
TEMP_DIR = SCRIPT_DIR / 'temp_proxies'

# Define available rules and their supported variants
AVAILABLE_RULES = {
    'unattached-policy': ['report-only', 'apply-and-report'],
    'sequential-js': ['report-only']
}


class ProxyBundle:
    # ... (The ProxyBundle class remains exactly the same as the previous version)
    # For brevity, it's omitted here. You can copy it from the previous response.
    """
    Represents an Apigee proxy bundle and provides methods to analyze and clean it.
    """
    def __init__(self, name: str, source_dir: Path):
        self.name = name
        self.source_dir = source_dir
        self.policies_dir = self.source_dir / 'policies'
        self.proxies_endpoint_dir = self.source_dir / 'proxies'
        self.targets_endpoint_dir = self.source_dir / 'targets'
        if not self.policies_dir.is_dir():
            raise FileNotFoundError(f"Policies directory not found for proxy '{name}' at {self.policies_dir}")
        self._all_policies, self._referenced_policies, self._unattached_policies, self._javascript_policies = None, None, None, None
    @property
    def all_policies(self) -> set[str]:
        if self._all_policies is None: self._all_policies = {p.stem for p in self.policies_dir.glob('*.xml')}
        return self._all_policies
    @property
    def referenced_policies(self) -> set[str]:
        if self._referenced_policies is None: self._referenced_policies = self._get_referenced_policy_names()
        return self._referenced_policies
    @property
    def unattached_policies(self) -> list[str]:
        if self._unattached_policies is None: self._unattached_policies = sorted(list(self.all_policies - self.referenced_policies))
        return self._unattached_policies
    @property
    def javascript_policies(self) -> set[str]:
        if self._javascript_policies is None: self._javascript_policies = self._get_javascript_policy_names()
        return self._javascript_policies
    def _get_javascript_policy_names(self) -> set[str]:
        js_names = set()
        for policy_file in self.policies_dir.glob('*.xml'):
            try:
                if ET.parse(policy_file).getroot().tag.lower() == 'javascript': js_names.add(policy_file.stem)
            except ET.ParseError: continue
        return js_names
    def find_sequential_js_steps(self) -> list[dict]:
        sequences, js_names = [], self.javascript_policies
        for endpoint_file in list(self.proxies_endpoint_dir.glob('*.xml')) + list(self.targets_endpoint_dir.glob('*.xml')):
            try:
                root = ET.parse(endpoint_file).getroot()
                containers = root.findall('.//PreFlow') + root.findall('.//PostFlow') + root.findall('.//Flow')
                for container in containers:
                    loc = f"Flow '{container.get('name')}'" if container.tag == 'Flow' and container.get('name') else container.tag
                    for path_element in [container.find('Request'), container.find('Response')]:
                        if path_element is None: continue
                        loc_path, seq = f"{loc}/{path_element.tag}", []
                        for step in path_element.findall('Step'):
                            name, cond = step.find('Name'), step.find('Condition')
                            is_valid = name is not None and name.text and name.text.strip() in js_names and cond is None
                            if is_valid: seq.append(name.text.strip())
                            else:
                                if len(seq) > 1: sequences.append({"file": endpoint_file.name, "location": loc_path, "sequence": seq})
                                seq = []
                        if len(seq) > 1: sequences.append({"file": endpoint_file.name, "location": loc_path, "sequence": seq})
            except ET.ParseError as e: logging.warning(f"[{self.name}] Could not parse endpoint file {endpoint_file.name}: {e}")
        return sequences
    def _get_referenced_policy_names(self) -> set[str]:
        referenced = set()
        for ep_dir in [self.proxies_endpoint_dir, self.targets_endpoint_dir]:
            if not ep_dir.exists(): continue
            for xml_file in ep_dir.glob('*.xml'):
                try:
                    for step in ET.parse(xml_file).getroot().findall('.//Step'):
                        name = step.find('Name')
                        if name is not None and name.text: referenced.add(name.text.strip())
                except ET.ParseError as e: logging.warning(f"Could not parse XML file {xml_file}: {e}")
        return referenced
    def _get_resource_url_from_policy_file(self, policy_file: Path) -> str | None:
        if not policy_file.exists(): return None
        try:
            root = ET.parse(policy_file).getroot()
            if root.tag.lower() in ('javascript', 'javacallout'):
                elem = root.find('ResourceURL')
                if elem is not None: return elem.text
        except ET.ParseError as e: logging.warning(f"Could not parse policy file {policy_file}: {e}")
        return None
    def generate_report_text(self) -> str:
        if not self.unattached_policies: return f"No unattached policies found in {self.name}.\n"
        return f"Unattached policies in {self.name}:\n" + "\n".join(f"  - {p}.xml" for p in self.unattached_policies) + "\n"
    def clean_and_save(self, output_base_dir: Path) -> Path:
        output_proxy_dir = output_base_dir / self.name / 'apiproxy'
        if output_proxy_dir.parent.exists(): shutil.rmtree(output_proxy_dir.parent)
        shutil.copytree(self.source_dir, output_proxy_dir)
        logging.info(f"[{self.name}] Copied source to {output_proxy_dir}")
        for policy_name in self.unattached_policies:
            policy_file = output_proxy_dir / 'policies' / f"{policy_name}.xml"
            resource_url = self._get_resource_url_from_policy_file(policy_file)
            if policy_file.exists(): policy_file.unlink()
            if resource_url:
                scheme, filename = resource_url.split('://')
                res_file = output_proxy_dir / 'resources' / scheme / filename
                if res_file.exists(): res_file.unlink()
        self._remove_orphaned_steps(output_proxy_dir)
        self._sync_manifest(output_proxy_dir)
        return output_proxy_dir
    def _remove_orphaned_steps(self, cleaned_proxy_dir: Path):
        remaining = {p.stem for p in (cleaned_proxy_dir / 'policies').glob('*.xml')}
        for xml_file in cleaned_proxy_dir.rglob('*.xml'):
            try:
                ET.register_namespace("", "http://www.w3.org/2001/XMLSchema")
                tree = ET.parse(xml_file)
                parents, changed = tree.getroot().findall('.//Step/..'), False
                for parent in parents:
                    for step in parent.findall('Step'):
                        name = step.find('Name')
                        if name is not None and name.text and name.text.strip() not in remaining:
                            parent.remove(step)
                            changed = True
                if changed: tree.write(xml_file, encoding='utf-8', xml_declaration=True)
            except Exception: pass
    def _sync_manifest(self, cleaned_proxy_dir: Path):
        for manifest_file in cleaned_proxy_dir.glob('*.xml'):
            try:
                ET.register_namespace("", "http://www.w3.org/2001/XMLSchema")
                tree = ET.parse(manifest_file)
                root = tree.getroot()
                self._update_manifest_section(root, 'Policies', 'Policy', [p.stem for p in sorted((cleaned_proxy_dir / 'policies').glob('*.xml'))])
                resources = []
                for res_type in ['jsc', 'java', 'py', 'xsl', 'wsdl', 'properties']:
                    res_dir = cleaned_proxy_dir / 'resources' / res_type
                    if res_dir.exists(): resources.extend(f'{res_type}://{r.name}' for r in sorted(res_dir.glob('*.*')))
                self._update_manifest_section(root, 'Resources', 'Resource', resources)
                tree.write(manifest_file, encoding='utf-8', xml_declaration=True)
            except Exception: pass
    def _update_manifest_section(self, root: ET.Element, section_tag: str, item_tag: str, items: list[str]):
        elem = root.find(section_tag)
        if elem is None: elem = ET.SubElement(root, section_tag)
        for child in list(elem): elem.remove(child)
        for text in items:
            item = ET.SubElement(elem, item_tag)
            item.text = text


# --- Helper and Execution Functions ---

def unzip_proxies(source_dir: Path, temp_dir: Path) -> Tuple[Dict[str, Path], Dict[str, int]]:
    # ... (This function remains the same)
    if temp_dir.exists(): shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    paths, sizes = {}, {}
    for zip_file in source_dir.glob('*.zip'):
        name = re.match(r'^(.*?)(?:_rev\d+_\d{4}_\d{2}_\d{2})?$', zip_file.stem).group(1)
        sizes[name] = zip_file.stat().st_size
        extract_dir = temp_dir / name
        with zipfile.ZipFile(zip_file, 'r') as zf: zf.extractall(extract_dir)
        apiproxy_dir = extract_dir / 'apiproxy'
        if apiproxy_dir.is_dir(): paths[name] = apiproxy_dir
    return paths, sizes


def zip_bundle(cleaned_dir: Path, zip_output_dir: Path) -> int:
    # ... (This function remains the same)
    zip_path = zip_output_dir / f'{cleaned_dir.parent.name}.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(cleaned_dir):
            for file in files:
                abs_path = Path(root) / file
                zf.write(abs_path, abs_path.relative_to(cleaned_dir.parent))
    return zip_path.stat().st_size


def generate_size_report(results: List[dict], report_path: Path):
    # ... (This function is modified to handle mixed variants better)
    if not results: return
    
    # Check if any rule was run in 'apply-and-report' mode
    is_apply_run = any(res['cleaned_size'] is not None for res in results)

    def to_mb(b): return b / (1024*1024)
    content = []
    
    if is_apply_run:
        content.extend(["# API Proxy Refactoring Summary", "| Proxy Name | Original Size (MB) | Cleaned Size (MB) | Reduction (MB) | Reduction (%) |", "|---|---|---|---|---|"])
        t_orig, t_clean = 0, 0
        for r in sorted(results, key=lambda x: x['name']):
            orig = r['original_size']
            # Use original size if cleaned size is not available (for report-only proxies in a mixed run)
            clean = r['cleaned_size'] if r['cleaned_size'] is not None else orig
            t_orig += orig
            t_clean += clean
            reduc_b, reduc_p = orig - clean, (orig - clean) / orig * 100 if orig > 0 else 0
            clean_str = f"{to_mb(clean):.3f}" if r['cleaned_size'] is not None else "N/A"
            reduc_b_str = f"**{to_mb(reduc_b):.3f}**" if r['cleaned_size'] is not None else "N/A"
            reduc_p_str = f"**{reduc_p:.2f}%**" if r['cleaned_size'] is not None else "N/A"
            content.append(f"| {r['name']} | {to_mb(orig):.3f} | {clean_str} | {reduc_b_str} | {reduc_p_str} |")
        t_reduc_b, t_reduc_p = t_orig - t_clean, (t_orig - t_clean) / t_orig * 100 if t_orig > 0 else 0
        content.append(f"| **Total** | **{to_mb(t_orig):.3f}** | **{to_mb(t_clean):.3f}** | **{to_mb(t_reduc_b):.3f}** | **{t_reduc_p:.2f}%** |")
    else: # Only report-only was run
        content.extend(["# API Proxy Analysis Report", "| Proxy Name | Original Size (MB) |", "|---|---|"])
        t_orig = sum(r['original_size'] for r in results)
        for r in sorted(results, key=lambda x: x['name']):
            content.append(f"| {r['name']} | {to_mb(r['original_size']):.3f} |")
        content.append(f"| **Total** | **{to_mb(t_orig):.3f}** |")

    with open(report_path, 'w') as f: f.write("\n".join(content))
    logging.info(f"Size summary report saved to: {report_path}")

def generate_sequential_js_report(results_by_proxy: Dict, report_path: Path):
    # ... (This function remains the same)
    report_lines, total_sequences_found = [], 0
    for proxy_name, sequences in sorted(results_by_proxy.items()):
        if sequences:
            report_lines.append(f"--- Found sequential JS steps in proxy: {proxy_name} ---")
            for seq_info in sequences:
                total_sequences_found += 1
                report_lines.append(f"  - Location: {seq_info['file']} -> {seq_info['location']}")
                report_lines.append(f"    Sequence: {', '.join(seq_info['sequence'])}")
            report_lines.append("")
    if not total_sequences_found:
        report_lines.append("No sequential, condition-less JavaScript steps found across all proxies.")
    with open(report_path, 'w') as f: f.write("\n".join(report_lines))
    logging.info(f"Sequential JS steps report saved to: {report_path}")

def run_unattached_policy_rule(proxy: ProxyBundle, variant: str) -> dict:
    """Executes the logic for the 'unattached-policy' rule for a single proxy."""
    logging.info(f"  - Running 'unattached-policy' ({variant}) on '{proxy.name}'...")
    report_text = proxy.generate_report_text()
    result = {'report_text': report_text, 'cleaned_size': None}

    if variant == 'apply-and-report':
        cleaned_dir = proxy.clean_and_save(OUTPUT_PROXIES_DIR)
        result['cleaned_size'] = zip_bundle(cleaned_dir, OUTPUT_PROXIES_DIR)
        
    return result

def run_sequential_js_rule(proxy: ProxyBundle) -> dict:
    """Executes the logic for the 'sequential-js' rule for a single proxy."""
    logging.info(f"  - Running 'sequential-js' (report-only) on '{proxy.name}'...")
    sequences = proxy.find_sequential_js_steps()
    return {'sequences': sequences} if sequences else {}

def parse_rule_arguments(rule_args: List[str]) -> Dict[str, str]:
    """Parses 'rule:variant' arguments into a dictionary, with validation."""
    parsed_rules = {}
    for arg in rule_args:
        if ':' not in arg:
            raise argparse.ArgumentTypeError(
                f"Invalid argument format: '{arg}'. Must be in 'rule:variant' format."
            )
        rule_name, variant = arg.split(':', 1)
        if rule_name not in AVAILABLE_RULES:
            raise argparse.ArgumentTypeError(
                f"Unknown rule: '{rule_name}'. Available rules: {list(AVAILABLE_RULES.keys())}"
            )
        if variant not in AVAILABLE_RULES[rule_name]:
            raise argparse.ArgumentTypeError(
                f"Unsupported variant '{variant}' for rule '{rule_name}'. "
                f"Supported variants: {AVAILABLE_RULES[rule_name]}"
            )
        parsed_rules[rule_name] = variant
    return parsed_rules

def main():
    parser = argparse.ArgumentParser(
        description="Analyzes and cleans Apigee proxy bundles based on specified rules.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'rules',
        nargs='+',
        help="One or more rules to execute, in 'rule:variant' format, separated by spaces.\n\n"
             "Example:\n"
             "  unattached-policy:apply-and-report sequential-js:report-only\n\n"
             "Available Rules and Variants:\n"
             "  - unattached-policy: [report-only, apply-and-report]\n"
             "  - sequential-js:     [report-only]"
    )
    args = parser.parse_args()

    try:
        rules_to_run = parse_rule_arguments(args.rules)
    except argparse.ArgumentTypeError as e:
        parser.error(e) # argparse will print the error and exit cleanly

    logging.info(f"Starting API Proxy tool with rules: {rules_to_run}")
    
    if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
    OUTPUT_PROXIES_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        unzipped_proxies, original_sizes = unzip_proxies(PROXIES_DIR, TEMP_DIR)
        if not unzipped_proxies:
            logging.warning(f"No proxy bundles found in {PROXIES_DIR}. Exiting.")
            return
        proxy_objects = [ProxyBundle(name, path) for name, path in unzipped_proxies.items()]
    except Exception as e:
        logging.error(f"Failed during initial setup (unzipping proxies): {e}", exc_info=True)
        return

    # --- Data collectors for final reports ---
    unattached_policy_reports = []
    sequential_js_results = {}
    size_report_data = []

    # --- Main Execution Loop ---
    # We loop through proxies first, then apply all requested rules to that proxy.
    # This is more efficient if rules share analysis steps in the future.
    for proxy in proxy_objects:
        logging.info(f"--- Processing Proxy: {proxy.name} ---")
        proxy_size_result = {'name': proxy.name, 'original_size': original_sizes.get(proxy.name, 0), 'cleaned_size': None}
        
        for rule_name, variant in rules_to_run.items():
            try:
                if rule_name == 'unattached-policy':
                    result = run_unattached_policy_rule(proxy, variant)
                    unattached_policy_reports.append(result['report_text'])
                    if result['cleaned_size'] is not None:
                        # Only one rule can provide a cleaned size per proxy
                        proxy_size_result['cleaned_size'] = result['cleaned_size']

                elif rule_name == 'sequential-js':
                    result = run_sequential_js_rule(proxy)
                    if result:
                        sequential_js_results[proxy.name] = result['sequences']

            except Exception as e:
                 logging.error(f"An error occurred while running rule '{rule_name}' on proxy '{proxy.name}': {e}", exc_info=True)
        
        size_report_data.append(proxy_size_result)


    # --- Final Report Generation ---
    if 'unattached-policy' in rules_to_run:
        with open(UNATTACHED_POLICIES_REPORT_PATH, 'w') as f:
            f.write("\n".join(unattached_policy_reports))
        logging.info(f"Unattached policies report saved to: {UNATTACHED_POLICIES_REPORT_PATH}")
        generate_size_report(size_report_data, SIZE_SUMMARY_REPORT_PATH)

    if 'sequential-js' in rules_to_run:
        generate_sequential_js_report(sequential_js_results, SEQUENTIAL_JS_REPORT_PATH)

    if TEMP_DIR.exists(): shutil.rmtree(TEMP_DIR)
    logging.info("Process finished successfully.")

if __name__ == '__main__':
    main()