"""sentinel completion — generate and install shell completion scripts."""

import os
import click


@click.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), default="zsh")
@click.option("--install", is_flag=True, help="Auto-install completion to your shell config")
def completion(shell: str, install: bool):
    """Generate or install shell completion script.

    \b
    Usage:
        sentinel completion zsh              # print completion script
        sentinel completion zsh --install    # auto-install to ~/.zshrc
        sentinel completion bash --install   # auto-install to ~/.bashrc
        sentinel completion fish --install   # auto-install to fish completions
    """
    env_var = "_SENTINEL_COMPLETE"

    if shell == "zsh":
        script = f'eval "$({env_var}=zsh_source sentinel)"'
        rc_file = os.path.expanduser("~/.zshrc")
    elif shell == "bash":
        script = f'eval "$({env_var}=bash_source sentinel)"'
        rc_file = os.path.expanduser("~/.bashrc")
    elif shell == "fish":
        script = f'{env_var}=fish_source sentinel | source'
        rc_file = os.path.expanduser("~/.config/fish/completions/sentinel.fish")

    if not install:
        click.echo(script)
        return

    # Auto-install
    marker = "# sentinel shell completion"

    if shell == "fish":
        # Fish uses a separate file
        os.makedirs(os.path.dirname(rc_file), exist_ok=True)
        with open(rc_file, "w") as f:
            f.write(f"{marker}\n{script}\n")
        click.echo(f"✓ Completion installed to {rc_file}")
    else:
        # Bash/zsh — append to rc file if not already present
        existing = ""
        if os.path.isfile(rc_file):
            with open(rc_file) as f:
                existing = f.read()

        if marker in existing:
            click.echo(f"✓ Completion already installed in {rc_file}")
        else:
            with open(rc_file, "a") as f:
                f.write(f"\n{marker}\n{script}\n")
            click.echo(f"✓ Completion installed to {rc_file}")

    click.echo(f"  Restart your shell or run: source {rc_file}")
