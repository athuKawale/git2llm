import os
from datetime import date
import click
from git2llm.auth import PATAuth
from git2llm.auth.token_store import save_token, clear_token
from git2llm.discovery import list_accessible_repos, select_repos
from git2llm.config import AppConfig, FilterConfig, CollectionConfig
from git2llm.writer import DatasetWriter
from git2llm.orchestrator import run_pipeline
from git2llm.utils.logging import setup_logging, logger

@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def cli(debug):
    """git2llm - Mine and filter GitHub repositories into LLM fine-tuning datasets."""
    setup_logging("DEBUG" if debug else "INFO")

@cli.command()
@click.option("--token", help="GitHub Personal Access Token (PAT)")
def auth(token):
    """Authenticate with GitHub using a Personal Access Token."""
    auth_provider = PATAuth(token)
    try:
        g = auth_provider.get_github_client()
        user = g.get_user()
        click.echo(click.style(f"Successfully authenticated as: {user.login}", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Authentication failed: {e}", fg="red"))

@cli.command()
def repos():
    """List accessible GitHub repositories."""
    auth_provider = PATAuth()
    try:
        g = auth_provider.get_github_client()
        repos_list = list_accessible_repos(g)
        if not repos_list:
            click.echo("No repositories found.")
            return
        
        click.echo(f"\nFound {len(repos_list)} accessible repositories:\n")
        for r in repos_list:
            click.echo(f"- {r.full_name:<40} [{r.visibility}] (★{r.stars})")
    except Exception as e:
        click.echo(click.style(f"Error: {e}", fg="red"))

@cli.command()
@click.option("--repos", "-r", multiple=True, help="Repositories to process (owner/repo)")
@click.option("--format", "-f", "output_format", default="alpaca", type=click.Choice(["alpaca", "sharegpt"]), help="Output schema format")
@click.option("--task", "-t", default="commit_message", type=click.Choice(["commit_message", "pr_review", "issue_to_patch", "all"]), help="Task type to generate")
@click.option("--output", "-o", default="./git2llm_output/", help="Output directory")
@click.option("--config", "config_file", help="Path to config YAML file")
@click.option("--workers", "-w", default=4, type=int, help="Parallel worker threads")
@click.option("--since", help="Earliest date to collect from (YYYY-MM-DD)")
@click.option("--languages", "-l", multiple=True, help="Filter files by programming language")
@click.option("--min-stars", default=0, type=int, help="Skip repositories below star count")
@click.option("--no-private", is_flag=True, help="Skip private repositories")
@click.option("--dry-run", is_flag=True, help="Run filtering without writing JSONL")
def run(repos, output_format, task, output, config_file, workers, since, languages, min_stars, no_private, dry_run):
    """Run the mining, filtering and generation pipeline."""
    # 1. Load config
    if config_file:
        try:
            app_config = AppConfig.load_from_yaml(config_file)
            logger.info(f"Loaded config from {config_file}")
        except Exception as e:
            click.echo(click.style(f"Error loading config file: {e}", fg="red"))
            return
    else:
        app_config = AppConfig()

    # 2. Authenticate
    auth_provider = PATAuth()
    try:
        g = auth_provider.get_github_client()
        token = auth_provider.get_token()
    except Exception as e:
        click.echo(click.style(f"Authentication failed. Please run 'git2llm auth' or set GIT2LLM_TOKEN. Error: {e}", fg="red"))
        return

    # 3. Discover/Select repos
    selected_repos = list(repos)
    if not selected_repos:
        # If no repos provided via CLI, load list and show interactive selector
        try:
            logger.info("Fetching accessible repositories...")
            all_repos = list_accessible_repos(g)
            
            # Apply quick CLI pre-filters
            if no_private:
                all_repos = [r for r in all_repos if r.visibility == "public"]
            if min_stars > 0:
                all_repos = [r for r in all_repos if r.stars >= min_stars]
                
            if not all_repos:
                click.echo("No repositories match filters.")
                return
                
            selected_repos = select_repos(all_repos)
            if not selected_repos:
                click.echo("No repositories selected.")
                return
        except Exception as e:
            click.echo(click.style(f"Error listing repositories: {e}", fg="red"))
            return

    # 4. Apply CLI parameter overrides to AppConfig
    app_config.output_format = output_format
    app_config.task = task
    app_config.max_workers = workers
    
    if since:
        try:
            app_config.collection.since = date.fromisoformat(since)
        except ValueError:
            click.echo(click.style("Invalid since date format. Use YYYY-MM-DD.", fg="red"))
            return

    # 5. Initialize Writer
    writer = DatasetWriter(output)

    # 6. Run pipeline
    try:
        run_pipeline(
            repos=selected_repos,
            config=app_config,
            token=token,
            writer=writer,
            dry_run=dry_run
        )
        
        # 7. Print summary report
        report = writer.generate_report(output_format, task)
        click.echo("\n" + "="*50)
        click.echo(click.style("Pipeline Completed Successfully!", fg="green", bold=True))
        click.echo(f"Run ID:          {report['run_id']}")
        click.echo(f"Duration:        {report['duration_seconds']}s")
        click.echo(f"Processed:       {len(report['repos_processed'])} repos")
        click.echo(f"Total Collected: {report['stats']['raw_commits_collected'] + report['stats']['raw_prs_collected']}")
        click.echo(f"Passed Filters:  {report['stats']['final_records']}")
        click.echo(f"Filter Rate:     {report['stats']['filter_rate_pct']}%")
        click.echo(f"Outputs written to: {os.path.abspath(output)}")
        click.echo("="*50 + "\n")
        
    except Exception as e:
        click.echo(click.style(f"Pipeline failed: {e}", fg="red"))
        raise e

if __name__ == "__main__":
    cli()
