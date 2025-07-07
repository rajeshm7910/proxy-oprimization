# Proxy Optimization Tool

A Python script that analyzes and cleans Apigee proxy bundles to identify issues and apply fixes based on best practices.

## Overview

This tool helps you maintain clean and efficient Apigee proxy bundles by:

- **Identifying unattached policies**: Finds policies that are defined but never referenced in proxy flows
- **Detecting sequential JavaScript steps**: Identifies JavaScript policies that run sequentially without conditions, which may indicate potential optimization opportunities
- **Cleaning proxy bundles**: Removes unused policies and their associated resources to reduce bundle size
- **Generating comprehensive reports**: Provides detailed analysis reports for review and decision-making

## Features

### Available Rules

1. **`unattached-policy`** - Identifies and optionally removes unused policies
   - **`report-only`**: Analyzes and reports unattached policies without making changes
   - **`apply-and-report`**: Removes unattached policies and generates cleaned proxy bundles

2. **`sequential-js`** - Detects sequential JavaScript policy executions
   - **`report-only`**: Identifies JavaScript policies that run in sequence without conditions

## Prerequisites

- Python 3.7 or higher
- Apigee proxy bundles in ZIP format

## Setup

1. **Clone or download the repository**
   ```bash
   git clone <repository-url>
   cd proxy-review
   ```

2. **Prepare your proxy bundles**
   - Place your Apigee proxy ZIP files in the `proxies/` directory
   - The tool expects proxy bundles in standard Apigee format (containing an `apiproxy` folder)

3. **Verify directory structure**
   ```
   proxy-review/
   ├── review.py
   ├── proxies/           # Place your proxy ZIP files here
   ├── output/           # Generated reports and cleaned proxies
   └── README.md
   ```

## Usage

### Basic Command Format

```bash
python review.py <rule>:<variant> [<rule>:<variant> ...]
```

### Examples

#### Example 1: Analyze unattached policies and apply fixes
```bash
python review.py unattached-policy:apply-and-report
```
This command will:
- Find all unattached policies in your proxy bundles
- Remove them from the proxy configurations
- Generate cleaned proxy bundles in `output/proxies/`
- Create a summary report in `output/unattached_policies_summary.txt`
- Generate a size comparison report in `output/refactor_summary_report.md`

#### Example 2: Report-only analysis of unattached policies
```bash
python review.py unattached-policy:report-only
```
This command will:
- Find all unattached policies in your proxy bundles
- Generate a report without making any changes
- Create a summary report in `output/unattached_policies_summary.txt`

#### Example 3: Analyze sequential JavaScript steps
```bash
python review_optimize.py sequential-js:report-only
```
This command will:
- Identify JavaScript policies that run sequentially without conditions
- Generate a report in `output/sequential_js_steps_report.txt`

#### Example 4: Combined analysis (as mentioned in your example)
```bash
python review.py unattached-policy:apply-and-report sequential-js:report-only
```
This command will:
- Remove unattached policies and generate cleaned bundles
- Analyze sequential JavaScript steps
- Generate comprehensive reports for both analyses

## Output Files

The tool generates several output files in the `output/` directory:

### Reports
- **`unattached_policies_summary.txt`**: List of unattached policies found in each proxy
- **`sequential_js_steps_report.txt`**: Details of sequential JavaScript policy executions
- **`refactor_summary_report.md`**: Size comparison table showing before/after bundle sizes

### Cleaned Proxies
- **`proxies/`**: Directory containing cleaned proxy bundles (when using `apply-and-report`)

## Understanding the Command Format

The command format `rule:variant` allows you to specify exactly what analysis to perform:

- **`unattached-policy:apply-and-report`**: 
  - Finds policies that exist in the `policies/` directory but are never referenced in proxy flows
  - Removes these policies and their associated resource files
  - Updates the proxy manifest to reflect the changes
  - Generates cleaned proxy bundles ready for deployment

- **`unattached-policy:report-only`**: 
  - Same analysis as above but doesn't make any changes
  - Useful for reviewing what would be cleaned before applying changes

- **`sequential-js:report-only`**: 
  - Scans proxy flows for JavaScript policies that execute sequentially without conditions
  - Helps identify potential optimization opportunities where policies could be combined

## Best Practices

1. **Always run in report-only mode first** to understand what changes would be made
2. **Review the generated reports** before applying any changes
3. **Test cleaned proxies** in a development environment before deploying to production
4. **Keep backups** of your original proxy bundles

## Troubleshooting

### Common Issues

1. **No proxy bundles found**: Ensure your ZIP files are in the `proxies/` directory
2. **Invalid argument format**: Make sure to use the `rule:variant` format (e.g., `unattached-policy:report-only`)
3. **Permission errors**: Ensure the script has read/write permissions in the directory

### Error Messages

- `Unknown rule`: Check that you're using one of the available rules (`unattached-policy`, `sequential-js`)
- `Unsupported variant`: Verify the variant is supported for the specified rule
- `Could not parse XML file`: The proxy bundle may be corrupted or in an unexpected format

## Contributing

To add new rules or modify existing functionality:

1. Update the `AVAILABLE_RULES` dictionary in `review.py`
2. Implement the rule logic in a new function
3. Add the rule execution to the main processing loop
4. Update this README with the new rule documentation

## License

This project is licensed under the terms specified in the LICENSE file.
