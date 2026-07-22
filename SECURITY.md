# Security

Do not open unknown model files, ComfyUI workflows, Blender scripts or Unity packages without reviewing them first. SFB is an offline toolchain and should not execute remote code by default.

The local API is scoped to the active workspace. It must not create direct HTTP
`shell` jobs, must reject string shell commands, and must not serve files outside
the workspace or artifact directories through `/api/file`.
Declared job outputs are also workspace-scoped: malformed, missing or
out-of-workspace `output_paths` fail the job rather than registering arbitrary
files as artifacts.

Report security concerns privately to the maintainers once the project has an official contact channel.
