"""
Badger Archive Data Source

Provides access to Badger optimization run archive with health monitoring.
Supports environment-based organization and nested date structure.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_timestamp_from_filename(filename: str) -> datetime | None:
    """
    Extract timestamp from Badger run filename.

    Filename pattern: {env}-YYYY-MM-DD-HHMMSS.yaml
    Examples:
        - lcls-2025-10-10-154343.yaml → 2025-10-10 15:43:43
        - sphere-2025-08-13-113025.yaml → 2025-08-13 11:30:25

    Args:
        filename: Badger run filename (just the filename, not full path)

    Returns:
        datetime object or None if parsing fails
    """
    try:
        # Remove .yaml extension
        name_without_ext = filename.replace('.yaml', '')

        # Split by '-' and get the last 4 parts (YYYY-MM-DD-HHMMSS)
        # Environment name can contain hyphens/underscores, so we count from the end
        parts = name_without_ext.split('-')

        if len(parts) < 5:  # At least env + YYYY + MM + DD + HHMMSS
            logger.warning(f"Filename doesn't match expected pattern: {filename}")
            return None

        # Extract date and time components (last 4 parts)
        year = parts[-4]
        month = parts[-3]
        day = parts[-2]
        time_str = parts[-1]  # HHMMSS format

        # Parse time components
        hour = time_str[:2]
        minute = time_str[2:4]
        second = time_str[4:6]

        # Create datetime object
        timestamp = datetime(
            int(year), int(month), int(day),
            int(hour), int(minute), int(second)
        )

        return timestamp

    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse timestamp from filename {filename}: {e}")
        return None


class BadgerArchiveDataSource:
    """
    Data source for accessing Badger optimization runs archive.

    The archive is organized as:
    - Environment-based: archive_root/{env_name}/YYYY/YYYY-MM/YYYY-MM-DD/{filename}.yaml
    - Filename pattern: {env}-YYYY-MM-DD-HHMMSS.yaml

    Provides methods to list, filter, and load run metadata without loading
    full evaluation data (which can be very large).
    """

    def __init__(self, archive_root: str):
        """
        Initialize data source with archive root path.

        Args:
            archive_root: Path to archive root directory

        Raises:
            FileNotFoundError: If archive root doesn't exist
        """
        self.archive_root = Path(archive_root)
        if not self.archive_root.exists():
            raise FileNotFoundError(
                f"Badger archive root not found: {archive_root}. "
                f"Please check OTTER_BADGER_ARCHIVE environment variable."
            )

        if not self.archive_root.is_dir():
            raise NotADirectoryError(
                f"Badger archive root is not a directory: {archive_root}"
            )

        logger.info(f"Initialized Badger archive data source: {self.archive_root}")

    def health_check(self) -> bool:
        """
        Check if archive is accessible and readable.

        Returns:
            bool: True if archive is healthy, False otherwise
        """
        try:
            # Check if archive root exists and is readable
            if not self.archive_root.exists():
                logger.error(f"Archive root does not exist: {self.archive_root}")
                return False

            if not self.archive_root.is_dir():
                logger.error(f"Archive root is not a directory: {self.archive_root}")
                return False

            # Check if we can list directories
            list(self.archive_root.iterdir())

            logger.debug("Badger archive health check passed")
            return True

        except Exception as e:
            logger.error(f"Badger archive health check failed: {e}")
            return False

    def list_runs(
        self,
        time_range: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None,
        beamline: Optional[str] = None
    ) -> List[str]:
        """
        List run filenames matching filters, sorted by run timestamp (newest first).

        Timestamps are extracted from filenames (e.g., lcls-2025-10-10-154343.yaml)
        rather than file modification times, making this robust to file copying/moving.

        Args:
            time_range: Optional dict with 'start' and 'end' datetime strings (ISO format)
            limit: Optional maximum number of runs to return (None = all)
            beamline: Optional beamline name filter (e.g., 'cu_hxr', 'cu_sxr', 'lcls_ii')

        Returns:
            List of relative paths from archive root
            Example: ['cu_hxr/2025/2025-09/2025-09-13/lcls-2025-09-13-065422.yaml', ...]
        """
        runs = []

        # Determine which beamline directories to search
        if beamline:
            beamline_dirs = [self.archive_root / beamline]
            # Validate beamline exists
            if not beamline_dirs[0].exists():
                logger.warning(f"Beamline directory not found: {beamline}")
                return []
        else:
            # Search all beamline directories (excluding hidden ones)
            try:
                beamline_dirs = [d for d in self.archive_root.iterdir() if d.is_dir() and not d.name.startswith('.')]
            except Exception as e:
                logger.error(f"Failed to list beamline directories: {e}")
                return []

        # Parse time range if provided
        start_time = None
        end_time = None
        if time_range:
            try:
                if 'start' in time_range:
                    start_time = datetime.fromisoformat(time_range['start'])
                if 'end' in time_range:
                    end_time = datetime.fromisoformat(time_range['end'])
            except ValueError as e:
                logger.warning(f"Invalid time range format: {e}")

        # Walk through beamline directories and collect run files
        for beamline_dir in beamline_dirs:
            try:
                # Walk the nested date structure
                for root, dirs, files in os.walk(beamline_dir):
                    # Filter out hidden directories (starting with '.')
                    dirs[:] = [d for d in dirs if not d.startswith('.')]

                    for filename in files:
                        # Skip hidden files and non-YAML files
                        if filename.startswith('.') or not filename.endswith('.yaml'):
                            continue

                        file_path = Path(root) / filename

                        # Extract timestamp from filename (more reliable than mtime)
                        file_timestamp = extract_timestamp_from_filename(filename)
                        if file_timestamp is None:
                            # Skip files that don't match expected naming pattern
                            logger.debug(f"Skipping file with non-standard name: {filename}")
                            continue

                        # Apply time filter if specified
                        if start_time or end_time:
                            if start_time and file_timestamp < start_time:
                                continue
                            if end_time and file_timestamp > end_time:
                                continue

                        # Store relative path and timestamp from filename
                        rel_path = file_path.relative_to(self.archive_root)
                        runs.append((str(rel_path), file_timestamp.timestamp()))

            except Exception as e:
                logger.warning(f"Failed to walk beamline directory {beamline_dir}: {e}")
                continue

        # Sort by modification time (newest first)
        runs.sort(key=lambda x: x[1], reverse=True)

        # Extract just the paths (remove mtime)
        run_paths = [run[0] for run in runs]

        # Apply limit if specified
        if limit is not None:
            run_paths = run_paths[:limit]

        logger.info(f"Found {len(run_paths)} runs matching filters")
        return run_paths

    def load_run_metadata(self, run_path: str) -> Dict[str, Any]:
        """
        Load minimal metadata from run file without full evaluation data.

        Args:
            run_path: Relative path from archive root to run file

        Returns:
            Dict containing:
                - name: Run name
                - timestamp: Run timestamp (datetime)
                - beamline: Beamline name from directory structure (e.g., 'cu_hxr', 'lcls_ii')
                - badger_environment: Badger environment name from run data (e.g., 'lcls', 'sphere')
                - algorithm: Generator/algorithm name
                - variables: List[Dict[str, List[float]]] - variables with ranges, e.g., [{'var1': [min, max]}, ...]
                - objectives: List[Dict[str, str]] - objectives with directions, e.g., [{'obj1': 'MAXIMIZE'}, ...]
                - constraints: List[Dict[str, Any]] - constraints in Badger VOCS format
                - num_evaluations: Number of evaluations performed
                - initial_values: Dict of initial objective values (if available)
                - min_values: Dict of minimum objective values across all evaluations (if available)
                - max_values: Dict of maximum objective values across all evaluations (if available)
                - final_values: Dict of final objective values (if available)
                - description: Run description
                - tags: Run tags

        Raises:
            FileNotFoundError: If run file doesn't exist
            yaml.YAMLError: If run file is corrupt
        """
        full_path = self.archive_root / run_path

        if not full_path.exists():
            raise FileNotFoundError(f"Run file not found: {run_path}")

        try:
            with open(full_path, 'r') as f:
                run_data = yaml.safe_load(f)

            # Extract metadata (avoiding loading full data dict which can be huge)
            metadata = {
                'name': run_data.get('name', 'Unknown'),
                'badger_environment': run_data.get('environment', {}).get('name', 'Unknown'),
                'algorithm': run_data.get('generator', {}).get('name', 'Unknown'),
                'description': run_data.get('description', ''),
                'tags': run_data.get('tags'),
            }

            # Extract beamline from directory path (first component)
            # Example: 'cu_hxr/2025/2025-10/2025-10-11/lcls-2025-10-11-200738.yaml' → 'cu_hxr'
            beamline_name = Path(run_path).parts[0] if run_path else 'Unknown'
            metadata['beamline'] = beamline_name

            # Get timestamp from filename (more reliable than mtime for copied/moved files)
            filename = Path(run_path).name
            file_timestamp = extract_timestamp_from_filename(filename)
            if file_timestamp:
                metadata['timestamp'] = file_timestamp
            else:
                # Fallback to mtime if filename parsing fails
                logger.warning(f"Could not parse timestamp from filename {filename}, using mtime")
                metadata['timestamp'] = datetime.fromtimestamp(full_path.stat().st_mtime)

            # Extract VOCS information in Badger's native format
            # Variables: {name: [min, max]} → [{name: [min, max]}, ...]
            # Objectives: {name: direction} → [{name: direction}, ...]
            vocs = run_data.get('vocs', {})

            variables_dict = vocs.get('variables', {})
            metadata['variables'] = [{name: ranges} for name, ranges in variables_dict.items()]

            objectives_dict = vocs.get('objectives', {})
            metadata['objectives'] = [{name: direction} for name, direction in objectives_dict.items()]

            constraints_dict = vocs.get('constraints', {})
            metadata['constraints'] = [{name: config} for name, config in constraints_dict.items()] if constraints_dict else []

            # Extract data summary without loading full data dict
            data = run_data.get('data', {})
            if data:
                # Count evaluations from one of the objective columns
                # Get first objective name from list of dicts
                objective_name = list(metadata['objectives'][0].keys())[0] if metadata['objectives'] else None
                if objective_name and objective_name in data:
                    metadata['num_evaluations'] = len(data[objective_name])
                else:
                    # Fallback: count keys in data dict
                    first_key = next(iter(data.keys()), None)
                    metadata['num_evaluations'] = len(data[first_key]) if first_key else 0

                # Try to extract objective statistics (init, min, max, last)
                if metadata['objectives'] and metadata['num_evaluations'] > 0:
                    try:
                        metadata['initial_values'] = {}
                        metadata['min_values'] = {}
                        metadata['max_values'] = {}
                        metadata['final_values'] = {}

                        # Extract objective names from list of dicts
                        objective_names = [list(obj_dict.keys())[0] for obj_dict in metadata['objectives']]

                        for obj in objective_names:
                            if obj in data:
                                # Get all objective values (keys are stringified indices)
                                obj_data = data[obj]
                                values = [obj_data[str(i)] for i in range(metadata['num_evaluations']) if str(i) in obj_data]

                                if values:
                                    metadata['initial_values'][obj] = values[0]
                                    metadata['min_values'][obj] = min(values)
                                    metadata['max_values'][obj] = max(values)
                                    metadata['final_values'][obj] = values[-1]
                    except Exception as e:
                        logger.warning(f"Failed to extract objective values: {e}")
                        metadata['initial_values'] = None
                        metadata['min_values'] = None
                        metadata['max_values'] = None
                        metadata['final_values'] = None
            else:
                metadata['num_evaluations'] = 0
                metadata['initial_values'] = None
                metadata['min_values'] = None
                metadata['max_values'] = None
                metadata['final_values'] = None

            return metadata

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse run file {run_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load run metadata from {run_path}: {e}")
            raise

    def get_most_recent_run(self, beamline: Optional[str] = None) -> Optional[str]:
        """
        Convenience method to get the most recent run filename.

        Args:
            beamline: Optional beamline name filter (e.g., 'cu_hxr', 'lcls_ii')

        Returns:
            Relative path to most recent run, or None if no runs found
        """
        runs = self.list_runs(limit=1, beamline=beamline)
        return runs[0] if runs else None
