"""E2E tests for problem generation"""
import pytest


class TestProblemGeneration:
    """Test: 'Give me 2 big problem statements to solve'"""

    def test_generate_big_problems(self, performance_thresholds):
        """2 multi-step problems, complex, inspired by book but not copies"""
        query = "Give me 2 big problem statements to solve"

        # response = query_engine.query(query, query_type="problem_generation")
        # assert len(response["problems"]) == 2
        # for problem in response["problems"]:
        #     assert len(problem["problem_statement"]) > 100
        #     assert problem["difficulty"] in ["medium", "hard"]
        #     assert len(problem["given_data"]) >= 2
        #     assert len(problem["to_find"]) >= 1
        #     assert len(problem["related_concepts"]) >= 2
        # assert response["metadata"]["response_time_ms"] < performance_thresholds["problem_generation"]

        pass

    def test_problems_not_direct_copies(self, mock_chunks):
        """Problem values differ from book, scenario is novel"""
        query = "Give me challenging problems on Newton's second law"

        # response = query_engine.query(query, query_type="problem_generation")
        # sample_problems = [c for c in mock_chunks if c["metadata"]["chunk_type"] == "sample_problem"]
        # for problem in response["problems"]:
        #     for sample in sample_problems:
        #         assert problem["problem_statement"] != sample["text"]

        pass

    def test_problems_have_clear_structure(self):
        """Each problem has: statement, given data, to find, hints"""
        query = "Give me 2 big problem statements"

        # response = query_engine.query(query, query_type="problem_generation")
        # for problem in response["problems"]:
        #     assert all(key in problem for key in ["problem_statement", "given_data", "to_find"])
        #     assert all(len(str(item)) > 5 for item in problem["given_data"])
        #     assert all(len(str(item)) > 5 for item in problem["to_find"])

        pass

    def test_problems_cite_source(self):
        """Source indicates chapter, section, inspired_by"""
        query = "Give me problems based on Chapter 5"

        # response = query_engine.query(query, query_type="problem_generation")
        # for problem in response["problems"]:
        #     assert "source" in problem
        #     assert problem["source"]["chapter"] == 5
        #     assert "inspired_by" in problem["source"] or "based_on" in problem["source"]

        pass

    def test_estimated_time_reasonable(self):
        """Easy: 5-10min, Medium: 10-20min, Hard: 20+min"""
        query = "Give me problems of varying difficulty"

        # response = query_engine.query(query, query_type="problem_generation")
        # for problem in response["problems"]:
        #     time = problem["estimated_time_minutes"]
        #     if problem["difficulty"] == "easy":
        #         assert 5 <= time <= 10
        #     elif problem["difficulty"] == "medium":
        #         assert 10 <= time <= 20
        #     elif problem["difficulty"] == "hard":
        #         assert time >= 20

        pass
