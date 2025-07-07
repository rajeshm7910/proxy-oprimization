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
- A configuration YAML file: `config_local.yaml` or `config_remote.yaml`

## Setup

1. **Clone or download the repository**
   ```bash
   git clone <repository-url>
   cd proxy-oprimization
   ```

2. **Prepare your proxy bundles**
   - Place your Apigee proxy ZIP files in the `proxies/` directory
   - The tool expects proxy bundles in standard Apigee format (containing an `apiproxy` folder)

3. **Verify directory structure**
   ```
   proxy-oprimization/
   ├── review_optimize.py
   ├── proxies/           # Place your proxy ZIP files here
   ├── output/           # Generated reports and cleaned proxies
   ├── config_local.yaml # Local mode config (see below)
   ├── config_remote.yaml # Remote mode config (see below)
   └── README.md
   ```

## Configuration

The tool requires a configuration YAML file, provided via the `--config` argument. Two example configs are provided:

- **Local mode (`config_local.yaml`)**: Use this if you want to analyze proxy bundles already present in the `proxies/` directory.
  ```yaml
  mode: local_proxy
  ```
- **Remote mode (`config_remote.yaml`)**: Use this to download deployed proxies from Apigee before analysis. Requires organization and environment info.
  ```yaml
  mode: remote_proxy
  org: <your-apigee-org>
  env: <your-apigee-env>
  # proxies: [optional, list of proxy names to download]
  ```
  You must also provide an OAuth2 token with the `--token` argument in remote mode.

## Usage

### Basic Command Format

```bash
python review_optimize.py --config <config_file.yaml> [--token <token>] <rule>:<variant> [<rule>:<variant> ...]
```

- Use `config_local.yaml` for local analysis, or `config_remote.yaml` for remote download and analysis.
- The `--token` argument is required only for remote mode.

### Examples

#### Example 1: Analyze unattached policies and apply fixes (local mode)
```bash
python review_optimize.py --config config_local.yaml unattached-policy:apply-and-report
```

#### Example 2: Report-only analysis of unattached policies (local mode)
```bash
python review_optimize.py --config config_local.yaml unattached-policy:report-only
```

#### Example 3: Analyze sequential JavaScript steps (local mode)
```bash
python review_optimize.py --config config_local.yaml sequential-js:report-only
```

#### Example 4: Combined analysis (local mode)
```bash
python review_optimize.py --config config_local.yaml unattached-policy:apply-and-report sequential-js:report-only
```

#### Example 5: Analyze unattached policies and apply fixes (remote mode)
```bash
python review_optimize.py --config config_remote.yaml --token <YOUR_OAUTH2_TOKEN> unattached-policy:apply-and-report
```

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


## License

This project is licensed under the terms specified in the LICENSE file.
