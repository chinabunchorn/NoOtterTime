from datetime import datetime


class Course:
    def __init__(self, course_name, user_id=None, course_id=None):
        self._course_id = course_id
        self._user_id = user_id
        self.set_course_name(course_name)

    def get_course_id(self): return self._course_id
    def get_course_name(self): return self._course_name
    def get_user_id(self): return self._user_id

    def set_course_name(self, name):
        if not name or not isinstance(name, str) or len(name.strip()) == 0:
            raise ValueError("Course name cannot be empty.")
        self._course_name = name.strip()

    def validate_name(self):
        forbidden_chars = ['<', '>', ';', '--']
        for char in forbidden_chars:
            if char in self._course_name:
                raise ValueError("Invalid characters in course name.")
        return True

    def to_dict(self):
        return {
            "course_id": self._course_id,
            "course_name": self._course_name,
            "user_id": self._user_id
        }


class StudySession:
    def __init__(self, course_id, start_time, end_time, goal_minutes, actual_minutes, task_type=None):

        if isinstance(start_time, str):
            start_time = start_time.replace('T', ' ')
        if isinstance(end_time, str):
            end_time = end_time.replace('T', ' ')
            
        self._course_id = course_id
        self._start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S") if isinstance(start_time, str) else start_time
        self._end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S") if isinstance(end_time, str) else end_time
        self.set_minutes(goal_minutes, actual_minutes)
        self._task_type = task_type

    def get_course_id(self): return self._course_id
    def get_goal_minutes(self): return self._goal_minutes
    def get_actual_minutes(self): return self._actual_minutes
    def get_task_type(self): return self._task_type
    def get_start_time(self): return self._start_time
    def get_end_time(self): return self._end_time

    def set_minutes(self, goal, actual):
        if goal < 0 or actual < 0:
            raise ValueError("Minutes cannot be negative.")
        self._goal_minutes = goal
        self._actual_minutes = actual

    def get_duration(self):
        delta = self._end_time - self._start_time
        return max(0, int(delta.total_seconds() / 60))

    def is_goal_met(self):
        return self._actual_minutes >= self._goal_minutes


class MoodEvaluation:
    def __init__(self, exhaustion, cynicism, efficacy):
        self.set_scores(exhaustion, cynicism, efficacy)

    def set_scores(self, exhaustion, cynicism, efficacy):
        for score in [exhaustion, cynicism, efficacy]:
            if not (0 <= score <= 3):
                raise ValueError("Scores must be between 0 and 3.")
        self._exhaustion_score = exhaustion
        self._cynicism_score = cynicism
        self._efficacy_score = efficacy

    def calculate_burnout_risk(self):
        risk_score = (self._exhaustion_score + self._cynicism_score + (6 - self._efficacy_score)) / 3
        if risk_score >= 4.0:
            return "High Risk"
        elif risk_score >= 2.5:
            return "Moderate Risk"
        return "Low Risk"