#!/usr/bin/env python3

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from sync_favorites import parse_mobile_feed_payload, parse_video_page, srt_segment_texts  # noqa: E402


class DouyinResolverTests(unittest.TestCase):
    def test_mobile_payload_requires_exact_id_and_prefers_highest_bitrate(self) -> None:
        payload = {
            "aweme_list": [
                {
                    "aweme_id": "9999",
                    "desc": "unrelated recommendation",
                    "video": {"play_addr": {"url_list": ["https://media.invalid/wrong.mp4"]}},
                },
                {
                    "aweme_id": "1234",
                    "desc": "requested video",
                    "video": {
                        "bit_rate": [
                            {"bit_rate": 100, "play_addr": {"url_list": ["https://media.invalid/low.mp4"]}},
                            {"bit_rate": 300, "play_addr": {"url_list": ["https://media.invalid/high.mp4"]}},
                        ],
                        "play_addr": {"url_list": ["https://media.invalid/fallback.mp4"]},
                    },
                },
            ]
        }
        result = parse_mobile_feed_payload(payload, "1234")
        self.assertEqual(result["video_id"], "1234")
        self.assertEqual(result["download_url"], "https://media.invalid/high.mp4")
        self.assertEqual(result["resolver"], "mobile_feed")

    def test_mobile_payload_rejects_random_recommendations(self) -> None:
        payload = {
            "aweme_list": [
                {
                    "aweme_id": "9999",
                    "video": {"play_addr": {"url_list": ["https://media.invalid/wrong.mp4"]}},
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "no exact match"):
            parse_mobile_feed_payload(payload, "1234")

    def test_mobile_payload_identifies_image_posts(self) -> None:
        payload = {"aweme_list": [{"aweme_id": "1234", "images": [{"url_list": ["https://image.invalid/1"]}]}]}
        with self.assertRaisesRegex(ValueError, "image post"):
            parse_mobile_feed_payload(payload, "1234")

    def test_legacy_parser_is_only_a_fallback(self) -> None:
        fallback = {
            "video_id": "1234",
            "title": "legacy",
            "download_url": "https://media.invalid/legacy.mp4",
            "public_url": "https://www.douyin.com/video/1234",
            "resolver": "legacy_share_page",
        }
        with patch("sync_favorites.parse_mobile_video", side_effect=ValueError("mobile unavailable")) as mobile:
            with patch("sync_favorites.parse_legacy_share_page", return_value=fallback) as legacy:
                result = parse_video_page("https://www.douyin.com/video/1234")
        self.assertEqual(result, fallback)
        mobile.assert_called_once_with("1234")
        legacy.assert_called_once_with("1234")


class SrtSegmentTests(unittest.TestCase):
    def test_extracts_ordered_segment_texts(self) -> None:
        srt = (
            "1\n00:00:00,031 --> 00:00:07,987\n我们希望每个人都财务自由\n\n"
            "2\n00:00:08,100 --> 00:00:12,000\n第二段\n跨行文本\n\n"
        )
        self.assertEqual(srt_segment_texts(srt), ["我们希望每个人都财务自由", "第二段 跨行文本"])

    def test_tolerates_missing_index_lines_and_blank_blocks(self) -> None:
        srt = "00:00:00,000 --> 00:00:02,000\n无编号段\n\n3\n00:00:05,000 --> 00:00:06,000\n\n"
        self.assertEqual(srt_segment_texts(srt), ["无编号段"])



class PortableDownloadTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.item = {"video_id": "1234", "url": "https://www.douyin.com/video/1234"}
        self.parsed = {"video_id": "1234", "title": "test", "download_url": "https://media.invalid/video.mp4"}

    def download(self, url, path):
        path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"fixture")

    def asr(self, video, folder, *args):
        (folder / "transcript.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
        (folder / "transcript.txt").write_text("hello\n")

    def test_download_then_transcribe_does_not_skip_or_redownload(self):
        from sync_favorites import run
        with patch("sync_favorites.parse_video_page", return_value=self.parsed), patch("sync_favorites.download", side_effect=self.download) as download:
            first = run([self.item], self.root)
            self.assertEqual(first['downloaded'], ['1234'])
            with patch('sync_favorites.transcribe_local', side_effect=self.asr) as asr:
                second = run([self.item], self.root, 'local')
                self.assertEqual(second['transcribed'], ['1234'])
                asr.assert_called_once()
            download.assert_called_once()

    def test_failed_transcription_can_resume_from_media(self):
        from sync_favorites import run
        with patch("sync_favorites.parse_video_page", return_value=self.parsed), patch("sync_favorites.download", side_effect=self.download) as download:
            with patch('sync_favorites.transcribe_local', side_effect=RuntimeError('missing model')):
                self.assertEqual(len(run([self.item], self.root, 'local')['failed']),1)
            with patch('sync_favorites.transcribe_local', side_effect=self.asr):
                self.assertEqual(run([self.item], self.root, 'local')['transcribed'],['1234'])
            download.assert_called_once()

    def test_manifest_id_mismatch_does_not_resolve_or_write_media(self):
        from sync_favorites import run
        with patch('sync_favorites.parse_video_page') as resolver:
            result = run([{**self.item,'video_id':'9999'}],self.root)
            resolver.assert_not_called()
            self.assertEqual(len(result['failed']),1)
            self.assertFalse((self.root/'9999').exists())

    def test_resolved_id_mismatch_does_not_download(self):
        from sync_favorites import run
        with patch('sync_favorites.parse_video_page', return_value={**self.parsed,'video_id':'9999'}), patch('sync_favorites.download') as download:
            self.assertEqual(len(run([self.item],self.root)['failed']),1)
            download.assert_not_called()

    def test_malformed_id_and_external_source_are_rejected(self):
        from sync_favorites import run
        with patch('sync_favorites.parse_video_page') as resolver:
            result = run([{'video_id':'../outside','url':self.item['url']},{**self.item,'url':'https://example.com/video/1234'}],self.root)
            resolver.assert_not_called()
            self.assertEqual(len(result['failed']),2)

    def test_throttle_stops_batch_and_does_not_fallback(self):
        from sync_favorites import run
        from urllib.error import HTTPError
        with patch('sync_favorites.parse_mobile_video',side_effect=HTTPError('https://example.com',429,'limited',{'Retry-After':'60'},None)), patch('sync_favorites.parse_legacy_share_page') as fallback:
            result = run([self.item,{'video_id':'9999','url':'https://www.douyin.com/video/9999'}],self.root)
            self.assertEqual(result['blocked']['retry_after'],'60')
            self.assertEqual(result['pending'],['9999'])
            fallback.assert_not_called()

    def test_lock_prevents_second_writer(self):
        from sync_favorites import run
        (self.root/'.download.lock').write_text('fixture')
        with self.assertRaisesRegex(RuntimeError,'locked'):
            run([self.item],self.root)
        self.assertEqual((self.root/'.download.lock').read_text(),'fixture')

    def test_empty_download_not_accepted(self):
        import io
        from sync_favorites import download
        destination=self.root/'video.mp4'
        with patch('sync_favorites.request',return_value=io.BytesIO(b'')):
            with self.assertRaisesRegex(ValueError,'empty'):
                download('https://media.invalid/empty.mp4',destination)
        self.assertFalse(destination.exists())

    def test_local_asr_uses_requested_executable_and_writes_transcript(self):
        from sync_favorites import transcribe_local
        video=self.root/'video.mp4';video.write_bytes(b'fixture')
        def fake_run(command, **kwargs):
            folder=Path(command[command.index('--output_dir')+1])
            (folder/'video.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nhello\n')
            self.assertEqual(command[0],'/custom/venv/bin/whisperx')
        with patch('sync_favorites.shutil.which',side_effect=lambda x:x),patch('sync_favorites.subprocess.run',side_effect=fake_run):
            result=transcribe_local(video,self.root,'/custom/venv/bin/whisperx','small','zh')
        self.assertEqual(result.read_text(),'hello\n')

    def test_cli_runs_offline_empty_manifest(self):
        import subprocess,json
        manifest=self.root/'items.json';manifest.write_text('{"items": []}')
        completed=subprocess.run([sys.executable,str(SCRIPTS_DIR/'sync_favorites.py'),'--items-file',str(manifest),'--output',str(self.root/'out')],capture_output=True,text=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['failed'],[])

    def test_unverified_cache_is_preserved_and_rejected(self):
        from sync_favorites import run
        folder=self.root/'1234';folder.mkdir()
        video=folder/'video.mp4';video.write_bytes(b'old-unverified-media')
        with patch('sync_favorites.parse_video_page') as resolver:
            result=run([self.item],self.root)
            resolver.assert_not_called()
        self.assertEqual(len(result['failed']),1)
        self.assertEqual(video.read_bytes(),b'old-unverified-media')
        self.assertFalse((folder/'metadata.json').exists())

    def test_html_response_is_not_saved_as_video(self):
        import io
        from sync_favorites import download
        destination=self.root/'video.mp4'
        with patch('sync_favorites.request',return_value=io.BytesIO(b'<html>verification</html>')):
            with self.assertRaisesRegex(ValueError,'not MP4'):
                download('https://media.invalid/test.mp4',destination)
        self.assertFalse(destination.exists())

    def test_legacy_part_symlink_is_never_opened(self):
        import io
        from sync_favorites import download
        outside=self.root/'outside.txt';outside.write_text('keep')
        destination=self.root/'video.mp4'
        try:
            destination.with_suffix('.mp4.part').symlink_to(outside)
        except OSError:
            self.skipTest('Symlink permission unavailable on this host')
        media=b'\x00\x00\x00\x18ftypisom'+b'fixture'
        with patch('sync_favorites.request',return_value=io.BytesIO(media)):
            download('https://media.invalid/test.mp4',destination)
        self.assertEqual(outside.read_text(),'keep')
        self.assertEqual(destination.read_bytes(),media)

if __name__ == "__main__":
    unittest.main()
