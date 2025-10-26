"""Utilities to parse Supreme Court judgment PDFs into a Python dictionary.

Usage:
 - Import `parse_judgments` and call with the path to the `supreme_court_judgments` folder.
 - Or run this file as a script to produce `parsed_judgments.json` in the current directory.

The parser uses PyPDF2 to extract text. If PyPDF2 is missing, the code raises a helpful ImportError.
"""
from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional
from PyPDF2 import PdfReader

def process_text(text: str) -> str:
	"""process the extracted text from each page.
	For example: 
	- Remove the watermark text "Indian Kanoon - http://indiankanoon.org/* using regex" 
	- replace -\n with empty string
	"""
	import re
	# Remove watermark text Indian Kanoon - http://indiankanoon.org/ {anything after} until the word ends
	cleaned_text = re.sub(r'Indian Kanoon - http://indiankanoon\.org/.*?\b', '', text)
	cleaned_text = re.sub(r'-\n', '', cleaned_text)
	return cleaned_text
def get_metadata(text):
	"""Extract metadata from the text of a judgment.

	Args:
		text: The full text of the judgment.
	Example:
	get the first time "Bench:" appear and extract until /n 
		"""
	
	metadata = {}
	import re
	# bench_match = re.search(r'Bench:\s*(.*?)\n', text) -> irrespective of case
	bench_match = re.search(r'Bench:\s*(.*?)\n', text, re.IGNORECASE)
	if bench_match:
		metadata['bench'] = bench_match.group(1).strip()
	return metadata
def parse_judgments(data_dir: str) -> Dict[str, Dict[str, Any]]:
	"""Walk `data_dir` and extract text from all PDFs.

	Args:
		data_dir: Path to the directory that contains the PDF files (e.g. data/supreme_court_judgments).

	Returns:
		A dictionary mapping a relative PDF path (relative to data_dir) to a metadata dict:
			{
				'filename': <filename>,
				'year': <immediate parent folder name if present else None>,
				'text': <extracted text or None on failure>,
				'num_pages': <int pages or None>,
				'error': <error message if extraction failed else None>
			}

	Notes:
		- Uses PyPDF2.PdfReader for text extraction.
	"""
	data_dir = os.path.abspath(data_dir)
	results: Dict[str, Dict[str, Any]] = {}
	# counter = 0
	for root, _dirs, files in os.walk(data_dir):
		print(f'Processing folder: {root}')
		for fname in files:
			if not fname.lower().endswith('.pdf'):
				continue

			abs_path = os.path.join(root, fname)
			rel_path = os.path.relpath(abs_path, data_dir)

			# Attempt to infer year from the parent folder name if it looks like a year
			parent = os.path.basename(os.path.dirname(abs_path))
			year = parent if parent.isdigit() and len(parent) == 4 else None

			entry = {
				'filename': fname,
				'year': year,
				'text': None,
				'num_pages': None,
				'error': None,
				'bench': None,
			}

			try:
				reader = PdfReader(abs_path)

				# PdfReader.pages is an indexable sequence
				num_pages = len(reader.pages)
				entry['num_pages'] = num_pages

				# Concatenate page text
				page_texts = []
				for i in range(num_pages):
					try:
						page = reader.pages[i]
						# PyPDF2 page.extract_text() may return None for some pages
						text = page.extract_text() or ''
						text = process_text(text)
						# extract metadata from the first page
						if i == 0:
							metadata = get_metadata(text)
							entry['bench'] = metadata.get('bench')
						page_texts.append(text)
					except Exception as e_page:
						# append a marker and continue
						page_texts.append('')
						# keep extraction going; record per-file error later
						entry['error'] = (entry['error'] or '') + f' page_{i}_error:{e_page};'

				entry['text'] = '\n'.join(page_texts).strip()
				if entry['text'] == '':
					# no textual content found
					entry['text'] = None
					if entry['error'] is None:
						entry['error'] = 'no_extracted_text'
				
			except Exception as e:  # capture file level errors
				entry['error'] = str(e)

			results[rel_path.replace('\\', '/')] = entry

	return results


def _atomic_write_json(path: str, obj: Any) -> None:
	"""Write JSON atomically by writing to a temp file then renaming.

	Prevents partially-written files if the process is interrupted mid-write.
	"""
	import tempfile

	dirname = os.path.dirname(os.path.abspath(path)) or '.'
	os.makedirs(dirname, exist_ok=True)
	fd, tmp_path = tempfile.mkstemp(prefix='.tmp_', suffix='.json', dir=dirname)
	try:
		with os.fdopen(fd, 'w', encoding='utf-8') as fh:
			json.dump(obj, fh, ensure_ascii=False, indent=2)
		os.replace(tmp_path, path)
	except Exception:
		# best effort cleanup
		try:
			if os.path.exists(tmp_path):
				os.unlink(tmp_path)
		except Exception:
			pass
		raise


def _process_single_pdf_worker(args):
	"""Extract text+metadata for a single PDF (worker-safe).

	Args is a tuple: (abs_path:str, rel_path:str, data_dir:str)
	Returns: (rel_path:str, entry:dict)
	"""
	abs_path, rel_path, data_dir = args
	entry = {
		'filename': os.path.basename(abs_path),
		'year': None,
		'text': None,
		'num_pages': None,
		'error': None,
		'bench': None,
	}

	# infer year
	parent = os.path.basename(os.path.dirname(abs_path))
	entry['year'] = parent if parent.isdigit() and len(parent) == 4 else None

	try:
		# local import to avoid pickling issues
		from PyPDF2 import PdfReader as _PdfReader
		reader = _PdfReader(abs_path)
		num_pages = len(reader.pages)
		entry['num_pages'] = num_pages

		page_texts = []
		for i in range(num_pages):
			try:
				page = reader.pages[i]
				text = page.extract_text() or ''
				text = process_text(text)
				if i == 0:
					metadata = get_metadata(text)
					entry['bench'] = metadata.get('bench')
				page_texts.append(text)
			except Exception as e_page:
				page_texts.append('')
				entry['error'] = (entry['error'] or '') + f' page_{i}_error:{e_page};'

		entry['text'] = '\n'.join(page_texts).strip() or None
		if entry['text'] is None and entry['error'] is None:
			entry['error'] = 'no_extracted_text'

	except Exception as e:
		entry['error'] = str(e)

	return rel_path.replace('\\', '/'), entry


def _flush_year_batch(year: str, rows: list, out_dir: str, fmt: str = 'jsonl') -> None:
	"""Flush a batch of rows for a given year to disk.

	- jsonl: writes a new chunk file per flush (year/part-<ts>.jsonl) atomically.
	- parquet: tries pandas+pyarrow; falls back to jsonl if not available.
	"""
	import time
	# no extra heavy imports here to keep flush light

	year_dir = os.path.join(out_dir, str(year))
	os.makedirs(year_dir, exist_ok=True)
	ts = int(time.time() * 1000)

	if fmt.lower() == 'parquet':
		try:
			import pandas as pd  # type: ignore
			# build DataFrame and write parquet atomically
			df = pd.DataFrame(rows)
			tmp_path = os.path.join(year_dir, f'.tmp-{ts}.parquet')
			final_path = os.path.join(year_dir, f'part-{ts}.parquet')
			df.to_parquet(tmp_path, index=False)
			os.replace(tmp_path, final_path)
			return
		except Exception:
			# fall back to jsonl
			pass

	# jsonl chunk fallback
	tmp_path = os.path.join(year_dir, f'.tmp-{ts}.jsonl')
	final_path = os.path.join(year_dir, f'part-{ts}.jsonl')
	with open(tmp_path, 'w', encoding='utf-8') as fh:
		for r in rows:
			fh.write(json.dumps(r, ensure_ascii=False) + '\n')
	os.replace(tmp_path, final_path)


def parse_judgments_parallel(
	data_dir: str,
	workers: int = 4,
	out_dir: Optional[str] = None,
	save_per_year: bool = True,
	save_every: int = 25,
	output_format: str = 'jsonl',
) -> Dict[str, Dict[str, Any]]:
	"""Parallel parsing with per-year partial saves.

	- Walks `data_dir`, submits each PDF to worker processes.
	- Buffers results per year and flushes periodically to out_dir/year/.
	- Returns an aggregated dict for in-memory use; if save_per_year is True,
	  the authoritative persisted results are the per-year files.
	"""
	from concurrent.futures import ProcessPoolExecutor, as_completed

	data_dir = os.path.abspath(data_dir)
	out_dir = os.path.abspath(out_dir) if out_dir else os.path.join(os.getcwd(), 'parsed_by_year')
	os.makedirs(out_dir, exist_ok=True)

	# discover pdfs
	pdf_tasks = []
	for root, _dirs, files in os.walk(data_dir):
		for f in files:
			if f.lower().endswith('.pdf'):
				abs_path = os.path.join(root, f)
				rel_path = os.path.relpath(abs_path, data_dir)
				pdf_tasks.append((abs_path, rel_path, data_dir))

	print(f'Total PDFs to process: {len(pdf_tasks)}')

	aggregated: Dict[str, Dict[str, Any]] = {}
	per_year_buffers: Dict[str, list] = {}

	with ProcessPoolExecutor(max_workers=workers) as ex:
		futures = [ex.submit(_process_single_pdf_worker, t) for t in pdf_tasks]
		completed = 0
		try:
			for fut in as_completed(futures):
				rel_path, entry = fut.result()
				year = entry.get('year') or 'unknown'
				aggregated[rel_path] = entry
				if save_per_year:
					buf = per_year_buffers.setdefault(year, [])
					buf.append({'rel_path': rel_path, **entry})
					if len(buf) >= save_every:
						_flush_year_batch(year, buf[:], out_dir, fmt=output_format)
						per_year_buffers[year].clear()
				completed += 1
				if completed % 50 == 0:
					print(f'Completed {completed}/{len(pdf_tasks)} PDFs...')
		except KeyboardInterrupt:
			print('KeyboardInterrupt received: flushing buffers and stopping...')
			# flush buffers
			for year, buf in per_year_buffers.items():
				if buf:
					_flush_year_batch(year, buf, out_dir, fmt=output_format)
			# re-raise so outer handlers can decide next
			raise
		finally:
			# final flush
			for year, buf in per_year_buffers.items():
				if buf:
					_flush_year_batch(year, buf, out_dir, fmt=output_format)

	return aggregated


def _iter_year_files(in_dir: str, input_format: str):
	"""Yield (year, file_path) for data part files under in_dir.

	Matches files like: <in_dir>/<year>/part-*.jsonl or part-*.parquet
	"""
	in_dir = os.path.abspath(in_dir)
	pattern = '.jsonl' if input_format == 'jsonl' else '.parquet'
	for entry in os.scandir(in_dir):
		if not entry.is_dir():
			continue
		year = entry.name
		year_dir = entry.path
		for f in os.scandir(year_dir):
			if f.is_file() and f.name.startswith('part-') and f.name.endswith(pattern):
				yield year, f.path


def consolidate_per_year(
	in_dir: str,
	out_path: str,
	input_format: str = 'jsonl',
	output_format: str = 'ndjson',
) -> None:
	"""Merge per-year chunk files into a single output file.

	- input_format: 'jsonl' or 'parquet' (must match how you saved the chunks)
	- output_format: 'ndjson' (streaming) or 'json' (single list; may be memory heavy)
	"""
	in_dir = os.path.abspath(in_dir)
	output_format = output_format.lower()
	input_format = input_format.lower()

	# prepare writer
	if output_format not in {'ndjson', 'json'}:
		raise ValueError("output_format must be 'ndjson' or 'json'")

	# For json output, we accumulate in memory (suitable for smaller datasets)
	accum = [] if output_format == 'json' else None

	if input_format == 'jsonl':
		# stream all jsonl parts
		if output_format == 'ndjson':
			# write streaming NDJSON atomically
			tmp = out_path + '.tmp'
			with open(tmp, 'w', encoding='utf-8') as out:
				for _year, file_path in _iter_year_files(in_dir, input_format):
					with open(file_path, 'r', encoding='utf-8') as fh:
						for line in fh:
							out.write(line)
			os.replace(tmp, out_path)
		else:
			# json list output
			for _year, file_path in _iter_year_files(in_dir, input_format):
				with open(file_path, 'r', encoding='utf-8') as fh:
					for line in fh:
						accum.append(json.loads(line))
			_atomic_write_json(out_path, accum)

	elif input_format == 'parquet':
		# use pandas to read parquet parts
		import pandas as pd  # type: ignore
		if output_format == 'ndjson':
			tmp = out_path + '.tmp'
			with open(tmp, 'w', encoding='utf-8') as out:
				for _year, file_path in _iter_year_files(in_dir, input_format):
					df = pd.read_parquet(file_path)
					for rec in df.to_dict(orient='records'):
						out.write(json.dumps(rec, ensure_ascii=False) + '\n')
			os.replace(tmp, out_path)
		else:
			for _year, file_path in _iter_year_files(in_dir, input_format):
				df = pd.read_parquet(file_path)
				accum.extend(df.to_dict(orient='records'))
			_atomic_write_json(out_path, accum)
	else:
		raise ValueError("input_format must be 'jsonl' or 'parquet'")


def _save_json(obj: Any, out_path: str) -> None:
	with open(out_path, 'w', encoding='utf-8') as fh:
		json.dump(obj, fh, ensure_ascii=False, indent=2)


if __name__ == '__main__':
	import argparse

	parser = argparse.ArgumentParser(description='Parse Supreme Court judgment PDFs into JSON')
	parser.add_argument(
		'data_dir',
		nargs='?',
		default=os.path.join('data', 'supreme_court_judgments'),
		help='Path to the directory that contains the judgment PDFs (default: data/supreme_court_judgments)'
	)
	parser.add_argument('--out', '-o', default='parsed_judgments.json', help='Output JSON file (for non-per-year aggregated run)')
	parser.add_argument('--parallel', action='store_true', help='Use parallel parsing and save per-year partial results')
	parser.add_argument('-w', '--workers', type=int, default=4, help='Number of worker processes for parallel parsing')
	parser.add_argument('--out-dir', default=None, help='Directory to write per-year files (default: ./parsed_by_year)')
	parser.add_argument('--save-every', type=int, default=25, help='Flush to disk every N files per year (parallel mode)')
	parser.add_argument('--format', choices=['jsonl', 'parquet'], default='jsonl', help='Per-year output format (parallel mode)')

	# consolidation options
	parser.add_argument('--consolidate', action='store_true', help='Consolidate per-year part files into a single output file')
	parser.add_argument('--in-dir', default=None, help='Input directory containing per-year outputs (default: ./parsed_by_year)')
	parser.add_argument('--input-format', choices=['jsonl', 'parquet'], default='jsonl', help='Input per-year file format')
	parser.add_argument('--out-format', choices=['ndjson', 'json'], default='ndjson', help='Output file format for consolidation')

	args = parser.parse_args()

	# Consolidation mode
	if args.consolidate:
		in_dir = args.in_dir or os.path.join(os.getcwd(), 'parsed_by_year')
		print(f'Consolidating files from: {in_dir} -> {args.out} (input={args.input_format}, output={args.out_format})')
		consolidate_per_year(
			in_dir=in_dir,
			out_path=args.out,
			input_format=args.input_format,
			output_format=args.out_format,
		)
		print('Consolidation complete.')
		raise SystemExit(0)

	print(f'Parsing PDFs under: {args.data_dir}')
	if args.parallel:
		try:
			parsed = parse_judgments_parallel(
				data_dir=args.data_dir,
				workers=args.workers,
				out_dir=args.out_dir,
				save_per_year=True,
				save_every=args.save_every,
				output_format=args.format,
			)
			print(f'Parsed {len(parsed)} PDFs. Per-year files written to {args.out_dir or os.path.join(os.getcwd(), "parsed_by_year")}')
		except KeyboardInterrupt:
			print('Interrupted! Per-year partial results have been flushed.')
		except Exception as e:
			print(f'Error occurred: {e}')
	else:
		# single-process legacy path with aggregated JSON
		parsed: Dict[str, Dict[str, Any]] = {}
		try:
			parsed = parse_judgments(args.data_dir)
			print(f'Parsed {len(parsed)} PDFs. Writing to {args.out}')
			_atomic_write_json(args.out, parsed)
		except KeyboardInterrupt:
			# best effort save whatever we have if any
			if parsed:
				_atomic_write_json(args.out, parsed)
			print(f'Interrupted! Partial aggregated results saved to {args.out}')
		except Exception as e:
			# save partial if any for debugging
			if parsed:
				_atomic_write_json(args.out, parsed)
			print(f'Error occurred: {e}')