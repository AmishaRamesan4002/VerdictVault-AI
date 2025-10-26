"""Utilities to parse Supreme Court judgment PDFs into a Python dictionary.

Usage:
 - Import `parse_judgments` and call with the path to the `supreme_court_judgments` folder.
 - Or run this file as a script to produce `parsed_judgments.json` in the current directory.

The parser uses PyPDF2 to extract text. If PyPDF2 is missing, the code raises a helpful ImportError.
"""
from __future__ import annotations

import os
import json
from typing import Dict, Any
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
	parser.add_argument('--out', '-o', default='parsed_judgments.json', help='Output JSON file')

	args = parser.parse_args()

	print(f'Parsing PDFs under: {args.data_dir}')
	# catch keyboard interrupt to save partial results
	try:
		parsed = parse_judgments(args.data_dir)
		print(f'Parsed {len(parsed)} PDFs. Writing to {args.out}')
		_save_json(parsed, args.out)
	except KeyboardInterrupt:
		_save_json(parsed, args.out)
		print(f'Interrupted! Partial results saved to {args.out}')
	except Exception as e:
		_save_json(parsed, args.out)
		print(f'Error occurred: {e}')