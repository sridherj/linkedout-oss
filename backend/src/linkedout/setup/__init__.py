# SPDX-License-Identifier: Apache-2.0
"""Setup infrastructure for LinkedOut OSS.

This package provides:
- Prerequisites detection (OS, PostgreSQL, Python, disk space)
- Setup-specific logging with correlation IDs and diagnostics
- Database setup (password, config, migrations, agent-context.env)
- Python environment setup (venv, dependencies, CLI verification)
- API key collection and validation (OpenAI, Apify)
- User profile setup (LinkedIn URL, affinity anchor)
- LinkedIn CSV import (auto-detect, guided UX)
- Contacts import (Google CSV, iCloud vCard)
- Seed data download and import (core/full datasets)
- Embedding generation orchestration
- Affinity computation orchestration
- Quantified readiness report generation
- Gap detection and interactive auto-repair
- Skill detection and installation for AI platforms
"""
from linkedout.setup.database import (
    generate_agent_context_env,
    generate_password,
    run_migrations,
    set_db_password,
    setup_database,
    verify_schema,
    write_config_yaml,
)
from linkedout.setup.logging_integration import (
    generate_diagnostic,
    get_setup_logger,
    init_setup_logging,
    log_step_complete,
    log_step_start,
)
from linkedout.setup.prerequisites import (
    DiskStatus,
    PlatformInfo,
    PostgresStatus,
    PrerequisiteReport,
    PythonStatus,
    check_disk_space,
    check_postgres,
    check_python,
    detect_platform,
    run_all_checks,
)
from linkedout.setup.api_keys import (
    collect_api_keys,
    collect_apify_key,
    collect_openai_key,
    prompt_embedding_provider,
    update_config_yaml,
    validate_openai_key,
    write_secrets_yaml,
)
from linkedout.setup.python_env import (
    create_venv,
    install_dependencies,
    pre_download_model,
    setup_python_env,
    verify_cli,
)
from linkedout.setup.user_profile import (
    create_user_profile,
    prompt_linkedin_url,
    setup_user_profile,
    validate_linkedin_url,
)
from linkedout.setup.csv_import import (
    copy_to_uploads,
    find_linkedin_csv,
    prompt_csv_path,
    run_csv_import,
    setup_csv_import,
)
from linkedout.setup.contacts_import import (
    find_contacts_file,
    prompt_contacts_format,
    prompt_contacts_import,
    run_contacts_import,
    setup_contacts_import,
)
from linkedout.setup.seed_data import (
    download_seed,
    import_seed,
    setup_seed_data,
    verify_seed_checksum,
)
from linkedout.setup.embeddings import (
    count_profiles_needing_embeddings,
    estimate_embedding_cost,
    estimate_embedding_time,
    run_embeddings,
    setup_embeddings,
)
from linkedout.setup.affinity import (
    check_user_profile_exists,
    format_tier_distribution,
    run_affinity_computation,
    setup_affinity,
)
from linkedout.setup.readiness import (
    ReadinessReport,
    collect_readiness_data,
    compute_coverage,
    detect_gaps,
    format_console_report,
    generate_readiness_report,
    save_report,
    suggest_next_steps,
)
from linkedout.setup.auto_repair import (
    RepairAction,
    analyze_gaps,
    execute_repair,
    prompt_repair,
    run_auto_repair,
)
from linkedout.setup.skill_install import (
    PlatformInfo,
    detect_platforms,
    generate_skills,
    install_skills_for_platform,
    setup_skills,
    update_dispatch_file,
)
from linkedout.setup.orchestrator import (
    SetupContext,
    SetupState,
    SetupStep,
    load_setup_state,
    run_setup,
    run_step,
    save_setup_state,
    should_run_step,
    validate_step_state,
)

__all__ = [
    # Logging
    "init_setup_logging",
    "get_setup_logger",
    "generate_diagnostic",
    "log_step_start",
    "log_step_complete",
    # Prerequisites
    "detect_platform",
    "check_postgres",
    "check_python",
    "check_disk_space",
    "run_all_checks",
    "PlatformInfo",
    "PostgresStatus",
    "PythonStatus",
    "DiskStatus",
    "PrerequisiteReport",
    # Database
    "generate_password",
    "set_db_password",
    "write_config_yaml",
    "run_migrations",
    "verify_schema",
    "generate_agent_context_env",
    "setup_database",
    # API Keys
    "prompt_embedding_provider",
    "collect_openai_key",
    "validate_openai_key",
    "collect_apify_key",
    "write_secrets_yaml",
    "update_config_yaml",
    "collect_api_keys",
    # User Profile
    "prompt_linkedin_url",
    "validate_linkedin_url",
    "create_user_profile",
    "setup_user_profile",
    # Python Environment
    "create_venv",
    "install_dependencies",
    "verify_cli",
    "pre_download_model",
    "setup_python_env",
    # CSV Import
    "find_linkedin_csv",
    "prompt_csv_path",
    "copy_to_uploads",
    "run_csv_import",
    "setup_csv_import",
    # Contacts Import
    "prompt_contacts_import",
    "prompt_contacts_format",
    "find_contacts_file",
    "run_contacts_import",
    "setup_contacts_import",
    # Seed Data
    "download_seed",
    "import_seed",
    "verify_seed_checksum",
    "setup_seed_data",
    # Embeddings
    "count_profiles_needing_embeddings",
    "estimate_embedding_time",
    "estimate_embedding_cost",
    "run_embeddings",
    "setup_embeddings",
    # Affinity
    "check_user_profile_exists",
    "run_affinity_computation",
    "format_tier_distribution",
    "setup_affinity",
    # Readiness
    "ReadinessReport",
    "collect_readiness_data",
    "compute_coverage",
    "detect_gaps",
    "suggest_next_steps",
    "generate_readiness_report",
    "format_console_report",
    "save_report",
    # Auto-Repair
    "RepairAction",
    "analyze_gaps",
    "prompt_repair",
    "execute_repair",
    "run_auto_repair",
    # Skill Installation
    "PlatformInfo",
    "detect_platforms",
    "generate_skills",
    "install_skills_for_platform",
    "update_dispatch_file",
    "setup_skills",
    # Orchestrator
    "SetupContext",
    "SetupState",
    "SetupStep",
    "load_setup_state",
    "save_setup_state",
    "should_run_step",
    "validate_step_state",
    "run_step",
    "run_setup",
]
