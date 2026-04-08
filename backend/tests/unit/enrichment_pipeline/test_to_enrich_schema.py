# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PostEnrichmentService._to_enrich_schema() transformer."""
from unittest.mock import MagicMock, patch

from linkedout.enrichment_pipeline.post_enrichment import PostEnrichmentService


def _make_service():
    """Create a PostEnrichmentService with mocked dependencies."""
    session = MagicMock()
    with patch.object(PostEnrichmentService, '_preload_companies'):
        svc = PostEnrichmentService(session)
    svc._company_by_canonical = {}
    return svc


class TestToEnrichSchema:
    """Tests for the Apify JSON -> EnrichProfileRequestSchema transformer."""

    def test_basic_experience_mapping(self):
        svc = _make_service()
        data = {
            'experience': [
                {
                    'position': 'Senior Engineer',
                    'companyName': 'Acme Corp',
                    'companyLinkedinUrl': 'https://linkedin.com/company/acme',
                    'companyUniversalName': 'acme-corp',
                    'employmentType': 'Full-time',
                    'startDate': {'month': 1, 'year': 2020},
                    'endDate': {'text': 'Present'},
                    'location': 'San Francisco',
                    'description': 'Building things',
                },
            ],
            'education': [],
            'skills': [],
        }
        result = svc._to_enrich_schema(data)

        assert len(result.experiences) == 1
        exp = result.experiences[0]
        assert exp.position == 'Senior Engineer'
        assert exp.company_name == 'Acme Corp'
        assert exp.company_linkedin_url == 'https://linkedin.com/company/acme'
        assert exp.company_universal_name == 'acme-corp'
        assert exp.employment_type == 'Full-time'
        assert exp.start_year == 2020
        assert exp.start_month == 1
        assert exp.is_current is True
        assert exp.location == 'San Francisco'
        assert exp.description == 'Building things'

    def test_month_string_parsing(self):
        """Month as string ("January", "Feb") should be parsed to int."""
        svc = _make_service()
        data = {
            'experience': [
                {
                    'position': 'Dev',
                    'startDate': {'month': 'January', 'year': 2020},
                    'endDate': {'month': 'Feb', 'year': 2021, 'text': 'Feb 2021'},
                },
            ],
        }
        result = svc._to_enrich_schema(data)
        exp = result.experiences[0]
        assert exp.start_month == 1
        assert exp.end_month == 2

    def test_is_current_from_present_text(self):
        """endDate.text == 'Present' (case-insensitive) sets is_current."""
        svc = _make_service()
        data = {
            'experience': [
                {'position': 'Dev', 'startDate': {'year': 2020}, 'endDate': {'text': 'present'}},
                {'position': 'Dev2', 'startDate': {'year': 2018}, 'endDate': {'year': 2019, 'text': 'Dec 2019'}},
            ],
        }
        result = svc._to_enrich_schema(data)
        assert result.experiences[0].is_current is True
        assert result.experiences[1].is_current is None

    def test_skills_merged_from_skills_and_top_skills(self):
        """skills (objects) + topSkills (strings) merged and deduped."""
        svc = _make_service()
        data = {
            'skills': [{'name': 'Python'}, {'name': 'Go'}],
            'topSkills': ['Python', 'Rust'],
        }
        result = svc._to_enrich_schema(data)
        assert result.skills == ['Python', 'Go', 'Rust']

    def test_skills_as_strings_handled(self):
        """skills array containing plain strings instead of dicts."""
        svc = _make_service()
        data = {
            'skills': ['Python', 'Go'],
        }
        result = svc._to_enrich_schema(data)
        assert result.skills == ['Python', 'Go']

    def test_empty_arrays_dont_crash(self):
        svc = _make_service()
        data = {
            'experience': [],
            'education': [],
            'skills': [],
            'topSkills': [],
        }
        result = svc._to_enrich_schema(data)
        assert result.experiences == []
        assert result.educations == []
        assert result.skills == []

    def test_null_arrays_dont_crash(self):
        svc = _make_service()
        data = {
            'experience': None,
            'education': None,
            'skills': None,
            'topSkills': None,
        }
        result = svc._to_enrich_schema(data)
        assert result.experiences == []
        assert result.educations == []
        assert result.skills == []

    def test_missing_keys_dont_crash(self):
        svc = _make_service()
        result = svc._to_enrich_schema({})
        assert result.experiences == []
        assert result.educations == []
        assert result.skills == []

    def test_non_integer_year_filtered_out(self):
        """Non-int year values should be None."""
        svc = _make_service()
        data = {
            'experience': [
                {
                    'position': 'Dev',
                    'startDate': {'year': '2020', 'month': 1},
                    'endDate': {'year': None},
                },
            ],
            'education': [
                {
                    'schoolName': 'MIT',
                    'startDate': {'year': 'N/A'},
                    'endDate': {'year': 2020},
                },
            ],
        }
        result = svc._to_enrich_schema(data)
        assert result.experiences[0].start_year is None
        assert result.experiences[0].end_year is None
        assert result.educations[0].start_year is None
        assert result.educations[0].end_year == 2020

    def test_education_mapping(self):
        svc = _make_service()
        data = {
            'education': [
                {
                    'schoolName': 'Stanford',
                    'schoolLinkedinUrl': 'https://linkedin.com/school/stanford',
                    'degree': 'MS',
                    'fieldOfStudy': 'Computer Science',
                    'startDate': {'year': 2015},
                    'endDate': {'year': 2017},
                    'description': 'Focus on AI',
                },
            ],
        }
        result = svc._to_enrich_schema(data)
        assert len(result.educations) == 1
        edu = result.educations[0]
        assert edu.school_name == 'Stanford'
        assert edu.school_linkedin_url == 'https://linkedin.com/school/stanford'
        assert edu.degree == 'MS'
        assert edu.field_of_study == 'Computer Science'
        assert edu.start_year == 2015
        assert edu.end_year == 2017
        assert edu.description == 'Focus on AI'

    def test_multiple_experiences_and_educations(self):
        svc = _make_service()
        data = {
            'experience': [
                {'position': 'CTO', 'startDate': {'year': 2022}, 'endDate': {'text': 'Present'}},
                {'position': 'VP Eng', 'startDate': {'year': 2019}, 'endDate': {'year': 2022}},
                {'position': 'SWE', 'startDate': {'year': 2015}, 'endDate': {'year': 2019}},
            ],
            'education': [
                {'schoolName': 'MIT', 'startDate': {'year': 2011}, 'endDate': {'year': 2015}},
                {'schoolName': 'High School', 'endDate': {'year': 2011}},
            ],
        }
        result = svc._to_enrich_schema(data)
        assert len(result.experiences) == 3
        assert len(result.educations) == 2


class TestParseMonthField:
    """Tests for the static _parse_month_field helper."""

    def test_int_passthrough(self):
        assert PostEnrichmentService._parse_month_field(6) == 6

    def test_string_full_name(self):
        assert PostEnrichmentService._parse_month_field('August') == 8

    def test_string_abbreviation(self):
        assert PostEnrichmentService._parse_month_field('Feb') == 2

    def test_none_returns_none(self):
        assert PostEnrichmentService._parse_month_field(None) is None

    def test_invalid_string_returns_none(self):
        assert PostEnrichmentService._parse_month_field('NotAMonth') is None
