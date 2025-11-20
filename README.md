# python-terragrunt

Small Python helpers to work with Terragrunt and OpenTofu/Terraform state.

- obtain OpenTofu/Terraform state using Terragrunt configuration found in your repo structure
- execute Terragrunt commands (buffered or live-streamed output)
- search for resource attributes within the retrieved state using ObjectPath queries

## Prerequisites
- Python ≥ 3.10
- Terragrunt & Terraform/OpenTofu should be available on PATH if you plan to run `terragrunt` commands
- State discovery via `terragrunt render` requires Terragrunt ≥ 0.77.18 (falls back to file search otherwise)
- AWS credentials for `boto3` to read remote state from S3 (env vars, instance profile or configured profile)

## Installation

```bash
pip install tha-terragrunt
```

## Quick start

### Read state and query it
Use `terragrunt.State` to locate and load remote state (S3) based on your Terragrunt configuration.  
By default the state is exposed as an ObjectPath tree, so you can run expressive queries.

```python
from terragrunt import State

# Directory inside your repo (e.g., a unit/service folder with a terragrunt.hcl,
# or a child folder when you have a top-level root.hcl).
state = State(
    path="/path/to/repo/services/api",  # defaults to current working directory
    path_limit="/path/to/repo",         # stop searching upwards here (default: '/')
    key_prefix="envs/prod",             # optional S3 key prefix
    key_filename="terraform.tfstate",   # default: 'terraform.tfstate'
    state_as_optree=True                # default: True (use ObjectPath tree)
)

if state.is_empty():
    raise SystemExit("No state found or it could not be loaded.")

# Get resource IDs for a given type (returns a tuple)
instance_ids = state.get_resources("aws_instance")
print("EC2 instances:", instance_ids)

# Query outputs (tuple of values)
outputs = state.query("$..outputs.*.value")
print("Outputs:", outputs)
```

A few more useful queries:
- all resource types present: `state.query("$..resources.*.type")`
- ARNs of IAM roles: `state.query("$..resources[@.type is 'aws_iam_role']..instances.attributes.arn")`
- S3 bucket names: `state.get_resources("aws_s3_bucket", id_name="id")`

To get raw JSON instead of an ObjectPath tree:
```python
raw_state = State(path=".", state_as_optree=False).data
```

### Run Terragrunt commands
Use `terragrunt.Process` to run Terragrunt with buffered or live output.

Buffered execution (capture stdout/stderr):
```python
import logging
from terragrunt import Process

logging.basicConfig(level=logging.INFO)

p = Process(
    cwd="/path/to/repo/services/api",
    cmd="plan",                # terragrunt subcommand
    opts="-no-color",          # terragrunt options
    tfopts="-input=false"      # forwarded to Terraform
)
rc = p.exec(live=False)        # buffered
print("return code:", rc)
print(p.output.stdout)         # captured output
```

Live execution (stream to logger or stdio):
```python
from terragrunt import Process

# Example: run-all apply with live streaming
p = Process(
    cwd="/path/to/repo/envs/prod",
    cmd="run-all apply",       # terragrunt command
    opts="-no-color",          # terragrunt options
    tfcmd="apply",             # underlying Terraform command (for run-all and similar)
    tfopts="-auto-approve"     # forwarded to Terraform
)
p.exec(live=True)              # streams to logging.INFO/ERROR by default

# If you prefer direct stdio streaming:
p.exec(live=True, std=True)    # writes to stdout/stderr
```

Notes:
- The library auto-handles the `--` separator for newer Terragrunt versions when `tfcmd` is provided.
- For simple commands like `terragrunt apply`, you can omit `tfcmd` and pass terraform options in `tfopts`.

## How state discovery works
`State` tries two strategies:
1) render mode (preferred, Terragrunt ≥ 0.77.18)
   - temporarily generates a minimal `terragrunt.hcl` that includes your root config (e.g., `root.hcl`)
   - runs `terragrunt render`, parses the rendered HCL, and extracts the S3 remote state `bucket` and `key`
2) search mode (fallback)
   - searches upwards (until `path_limit`) for one of: your `config` (default `root.hcl`), `terragrunt.hcl`, or `terraform.tfvars`
   - reads the `remote_state` block and calculates the S3 key as `<key_prefix>/<relative_path>/<key_filename>`

If the object exists in S3, it is downloaded and parsed as JSON.

## Minimal API overview
- `terragrunt.State(path='.', path_limit='/', config='root.hcl', key_prefix=None, key_filename='terraform.tfstate', state_as_optree=True)`
  - `.data`: ObjectPath tree by default, or raw dict if `state_as_optree=False`
  - `.query(q)`: run an ObjectPath query, returns a tuple
  - `.get_resources(type_name, id_name='id')`: return tuple of resource IDs
  - `.is_empty()`: True if no state was loaded
- `terragrunt.Process(cwd=None, cmd, opts='', tfcmd=None, tfopts='')`
  - `.get_version()`: Terragrunt version tuple
  - `.exec(live=False, std=False)`: run the command; when `live=True` streams output
  - `.output`: completed process output (`subprocess.CompletedProcess`) when `live=False`

## Logging
This package uses Python’s `logging` module. For example:
```python
import logging
logging.basicConfig(level=logging.INFO)
```

## License
See `LICENSE`.
