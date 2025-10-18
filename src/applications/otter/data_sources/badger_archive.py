"""
Badger Archive Data Source

Provides access to Badger optimization run archive with health monitoring.
Supports environment-based organization and nested date structure.
"""

import os
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
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

    def __init__(
        self,
        archive_root: str,
        use_cache: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        """
        Initialize data source with archive root path.

        Args:
            archive_root: Path to archive root directory
            use_cache: Whether to use cached index (default: True)
            progress_callback: Optional callback(current, total, path) for index building progress

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

        # Load or build index
        self.index: Optional[Dict[str, Any]] = None
        if use_cache:
            self.index = self._load_cache()

        if self.index is None:
            logger.info("Building fresh index (this may take a few minutes)...")
            self.index = self._build_index(progress_callback=progress_callback)
            if use_cache:
                self._save_cache(self.index)

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

    def _get_cache_path(self) -> Path:
        """Get path to cache file."""
        return self.archive_root / ".otter_index.json"

    def _save_cache(self, index: Dict[str, Any]) -> None:
        """Save index to cache file."""
        cache_path = self._get_cache_path()
        try:
            with open(cache_path, 'w') as f:
                json.dump(index, f, indent=2)
            logger.info(f"Saved index cache to {cache_path} ({index['total_runs']} runs)")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Load index from cache file."""
        cache_path = self._get_cache_path()
        try:
            with open(cache_path, 'r') as f:
                index = json.load(f)
            logger.info(f"Loaded index cache from {cache_path} ({index.get('total_runs', 0)} runs)")
            return index
        except FileNotFoundError:
            logger.info("No cache file found")
            return None
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return None

    def _build_index(self, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> Dict[str, Any]:
        """
        Build complete index with full metadata for all runs.

        Args:
            progress_callback: Optional callback(current, total, path) for progress updates

        Returns:
            Index dict with metadata for all runs
        """
        index = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "runs": []
        }

        # Collect all visible YAML files
        all_files = []
        for beamline_dir in self.archive_root.iterdir():
            if not beamline_dir.is_dir() or beamline_dir.name.startswith('.'):
                continue
            for root, dirs, files in os.walk(beamline_dir):
                # Filter out hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for filename in files:
                    if filename.endswith('.yaml') and not filename.startswith('.'):
                        all_files.append(Path(root) / filename)

        total = len(all_files)
        logger.info(f"Found {total} run files to index")

        # Initial progress update
        if progress_callback:
            progress_callback(0, total, "start")

        # Load metadata for each file
        for file_path in all_files:
            try:
                # Load full metadata using existing method
                rel_path = str(file_path.relative_to(self.archive_root))
                metadata = self.load_run_metadata(rel_path)

                # Convert to serializable format (datetime -> string)
                serializable_metadata = {
                    "run_filename": rel_path,
                    "timestamp": metadata["timestamp"].isoformat(),
                    "run_name": metadata["name"],
                    "beamline": metadata["beamline"],
                    "badger_environment": metadata["badger_environment"],
                    "algorithm": metadata["algorithm"],
                    "variables": metadata["variables"],
                    "objectives": metadata["objectives"],
                    "constraints": metadata.get("constraints", []),
                    "num_evaluations": metadata["num_evaluations"],
                    "initial_objective_values": metadata.get("initial_values"),
                    "min_objective_values": metadata.get("min_values"),
                    "max_objective_values": metadata.get("max_values"),
                    "final_objective_values": metadata.get("final_values"),
                    "description": metadata.get("description", ""),
                    "tags": metadata.get("tags")
                }

                index["runs"].append(serializable_metadata)

            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")
                continue

        # Final progress update
        if progress_callback:
            progress_callback(total, total, "complete")

        index["total_runs"] = len(index["runs"])

        # Sort by timestamp (newest first) for efficient filtering
        index["runs"].sort(key=lambda r: r["timestamp"], reverse=True)

        logger.info(f"Built index with {index['total_runs']} runs")
        return index

    def list_runs(
        self,
        time_range: Optional[Dict[str, str]] = None,
        limit: Optional[int] = None,
        beamline: Optional[str] = None,
        algorithm: Optional[str] = None,
        badger_environment: Optional[str] = None,
        objective: Optional[str] = None,
        sort_order: str = "newest_first"
    ) -> List[str]:
        """
        List run filenames matching filters, sorted by run timestamp.

        Uses cached index for instant filtering. All filters are applied in-memory.

        Args:
            time_range: Optional dict with 'start' and 'end' datetime strings (ISO format)
            limit: Optional maximum number of runs to return (None = all)
            beamline: Optional beamline name filter (e.g., 'cu_hxr', 'cu_sxr', 'lcls_ii')
            algorithm: Optional algorithm/generator name filter (e.g., 'expected_improvement', 'neldermead')
            badger_environment: Optional Badger environment name filter (e.g., 'lcls', 'sphere')
            objective: Optional objective name filter (e.g., 'pulse_intensity_p80')
            sort_order: Sort order - 'newest_first' (default) or 'oldest_first'

        Returns:
            List of relative paths from archive root
            Example: ['cu_hxr/2025/2025-09/2025-09-13/lcls-2025-09-13-065422.yaml', ...]

        Note:
            Filtering is now instant using the cached index. No file I/O required for filtering.
        """
        if self.index is None:
            logger.error("Index not loaded, cannot list runs")
            return []

        # Start with all runs (already sorted by timestamp newest first in index)
        matching_runs = self.index["runs"]

        # Apply time range filter
        if time_range:
            start_str = time_range.get('start')
            end_str = time_range.get('end')

            matching_runs = [
                r for r in matching_runs
                if (not start_str or r["timestamp"] >= start_str) and
                   (not end_str or r["timestamp"] <= end_str)
            ]

        # Apply beamline filter
        if beamline:
            matching_runs = [r for r in matching_runs if r["beamline"] == beamline]

        # Apply algorithm filter
        if algorithm:
            matching_runs = [r for r in matching_runs if r["algorithm"] == algorithm]

        # Apply badger environment filter
        if badger_environment:
            matching_runs = [r for r in matching_runs if r["badger_environment"] == badger_environment]

        # Apply objective filter (check if objective exists in any of the objective dicts)
        if objective:
            matching_runs = [
                r for r in matching_runs
                if any(objective in obj_dict for obj_dict in r["objectives"])
            ]

        # Apply sorting based on sort_order
        if sort_order == "oldest_first":
            # Reverse the order (index is newest_first by default)
            matching_runs = list(reversed(matching_runs))
        # else: sort_order == "newest_first" is already the default order from index

        # Apply limit after sorting
        if limit is not None:
            matching_runs = matching_runs[:limit]

        # Extract just the file paths
        run_paths = [r["run_filename"] for r in matching_runs]

        logger.info(f"Found {len(run_paths)} runs matching filters (sort_order={sort_order})")
        return run_paths

    def load_run_metadata(self, run_path: str) -> Dict[str, Any]:
        """
        Load minimal metadata from run file without full evaluation data.

        Uses cached index data if available, otherwise loads from file.

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
        # Try to get from index first
        if self.index:
            for run in self.index["runs"]:
                if run["run_filename"] == run_path:
                    # Convert back to expected format (string -> datetime)
                    return {
                        "name": run["run_name"],
                        "timestamp": datetime.fromisoformat(run["timestamp"]),
                        "beamline": run["beamline"],
                        "badger_environment": run["badger_environment"],
                        "algorithm": run["algorithm"],
                        "variables": run["variables"],
                        "objectives": run["objectives"],
                        "constraints": run.get("constraints", []),
                        "num_evaluations": run["num_evaluations"],
                        "initial_values": run.get("initial_objective_values"),
                        "min_values": run.get("min_objective_values"),
                        "max_values": run.get("max_objective_values"),
                        "final_values": run.get("final_objective_values"),
                        "description": run.get("description", ""),
                        "tags": run.get("tags")
                    }

        # Fallback: load from file if not in index
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
                                    # Filter out None values for min/max calculation
                                    numeric_values = [v for v in values if v is not None]
                                    if numeric_values:
                                        metadata['min_values'][obj] = min(numeric_values)
                                        metadata['max_values'][obj] = max(numeric_values)
                                    else:
                                        metadata['min_values'][obj] = None
                                        metadata['max_values'][obj] = None
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

    def get_most_recent_run(
        self,
        beamline: Optional[str] = None,
        algorithm: Optional[str] = None,
        badger_environment: Optional[str] = None,
        objective: Optional[str] = None
    ) -> Optional[str]:
        """
        Convenience method to get the most recent run filename.

        Args:
            beamline: Optional beamline name filter (e.g., 'cu_hxr', 'lcls_ii')
            algorithm: Optional algorithm/generator name filter (e.g., 'expected_improvement')
            badger_environment: Optional Badger environment name filter (e.g., 'lcls')
            objective: Optional objective name filter (e.g., 'pulse_intensity_p80')

        Returns:
            Relative path to most recent run, or None if no runs found
        """
        runs = self.list_runs(
            limit=1,
            beamline=beamline,
            algorithm=algorithm,
            badger_environment=badger_environment,
            objective=objective
        )
        return runs[0] if runs else None
