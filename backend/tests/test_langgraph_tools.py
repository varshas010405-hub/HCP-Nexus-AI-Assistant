import unittest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.models import Doctor, Interaction
from backend.langgraph import tools as tools_mod


class LangGraphToolTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session = self.session_factory()
        tools_mod.SessionLocal = lambda: self.session_factory()

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def _create_interaction(self, doctor_name, hospital, products, visit_date, interest_level="Medium"):
        doctor = Doctor(
            name=doctor_name,
            hospital=hospital,
            specialization="Cardiology",
            department="Cardiology Dept",
        )
        self.session.add(doctor)
        self.session.commit()

        interaction = Interaction(
            user_id=1,
            doctor_id=doctor.id,
            doctor_name=doctor.name,
            hospital=doctor.hospital,
            specialization=doctor.specialization,
            department=doctor.department,
            visit_date=visit_date,
            products=products,
            summary="Test summary",
            notes="Test notes",
            interest_level=interest_level,
            followup_date=visit_date,
        )
        self.session.add(interaction)
        self.session.commit()
        return interaction

    def test_search_interaction_tool_supports_structured_filters(self):
        self._create_interaction("Rajesh Patel", "Apollo Hospital", "CardioPlus", date(2026, 7, 10))
        self._create_interaction("Sarah Jenkins", "Metro Clinic", "DiabeCare", date(2026, 7, 11))

        response = tools_mod.search_interaction_tool(
            query_str="",
            filters={"doctor_name": "Rajesh", "hospital": "Apollo", "product": "CardioPlus", "date": "2026-07-10"},
        )

        self.assertTrue(response["success"])
        self.assertEqual(len(response["results"]), 1)
        self.assertEqual(response["results"][0]["doctor_name"], "Rajesh Patel")
        self.assertEqual(response["results"][0]["hospital"], "Apollo Hospital")

    def test_normalize_extracted_payload_does_not_inject_placeholders(self):
        payload = tools_mod.normalize_extracted_payload({
            "doctor_name": "",
            "hospital": "",
            "specialization": "",
            "department": "",
            "visit_date": "",
            "products": [],
            "interest_level": "",
        })

        self.assertIsNone(payload)

    def test_simulate_llm_extracts_interest_from_simple_phrase(self):
        user_text = "I met Dr Rajesh Patel at Apollo Hospital today. Discussed CardioPlus, interest was high, followup next Monday."
        extracted = tools_mod.simulate_llm("Information Extraction Unit", user_text)
        self.assertIn("interest_level", extracted)
        self.assertTrue("high" in extracted.lower() or "High" in extracted)


if __name__ == "__main__":
    unittest.main()
