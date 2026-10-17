"""Render native teacher previews against disposable WSGI state, with egress denied."""
from html.parser import HTMLParser
from pathlib import Path
import json
import unittest

import qualify_account_startup_repair as fixture


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_title = False
        self.title = []
        self.body = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        (self.title if self.in_title else self.body).append(data)


class TeacherRendering(unittest.TestCase):
    def test_native_programme_previews_keep_sections_out_of_titles(self):
        client = fixture.authenticated()
        for programme in ('fsc1', 'fsc2', 'mdcat'):
            with self.subTest(programme=programme):
                entry = fixture.enter_preview(client, 'teacher:' + programme)
                self.assertEqual(entry.status_code, 302)
                result = client.get('/teacher', base_url='https://localhost')
                self.assertEqual(result.status_code, 200)
                home = Document(result.get_data(as_text=True))
                self.assertEqual(''.join(home.title).strip(), 'Teacher Home · ScoreMax')
                body = ' '.join(home.body)
                self.assertIn('Teacher tools and programme context', body)
                self.assertIn('Your referral code:', body)
                self.assertIn('Read-only synthetic view', body)
                with fixture.sm.db() as conn:
                    teacher = fixture.user('ux-teacher')
                    classes = conn.execute('SELECT id FROM classrooms WHERE teacher_id=? ORDER BY id', (teacher['id'],)).fetchall()
                self.assertEqual(len(classes), 2)
                for classroom in classes:
                    result = client.get('/teacher/class/' + str(classroom['id']), base_url='https://localhost')
                    self.assertEqual(result.status_code, 200)
                    page = Document(result.get_data(as_text=True))
                    self.assertEqual(''.join(page.title).strip(), 'Class Overview · ScoreMax')
                    self.assertIn('Assessment structure', ' '.join(page.body))
                    self.assertIn('Issue quiz to class', ' '.join(page.body))
                ended = client.get('/admin/view-as/exit', base_url='https://localhost', follow_redirects=True)
                self.assertEqual(ended.status_code, 200)
                self.assertIn('You are back in ScoreMax Admin', ended.get_data(as_text=True))
        with fixture.sm.db() as conn:
            for table in ('questions', 'attempts', 'assessment_sessions', 'assignments'):
                exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
                if exists:
                    self.assertEqual(conn.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], 0, table)

    def test_content_insertion_rejects_ambiguous_blocks(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ux_vnext_overlay.ux_teacher_workspace import _append_content
        with self.assertRaisesRegex(SystemExit, 'CONTENT_END_MISMATCH'):
            _append_content('{% block content %}{% endblock %}{% endblock %}', '<section>example</section>', 'TEST')
        with self.assertRaisesRegex(SystemExit, 'CONTENT_BLOCK_MISMATCH'):
            _append_content('{% block title %}title{% endblock %}', '<section>example</section>', 'TEST')


if __name__ == '__main__':
    unittest.main()
