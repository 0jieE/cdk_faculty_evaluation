from django.urls import include, path, re_path

from .views import academics, auth, faculty, people, records, staff, student

student_patterns = [
    path("", student.home, name="home"),
    path("evaluate/<int:faculty_class_id>/", student.evaluate, name="evaluate"),
]

faculty_patterns = [
    path("", faculty.home, name="home"),
    path("classes/<int:pk>/", faculty.class_detail, name="class"),
    path("classes/<int:pk>/pdf/", faculty.class_pdf, name="class_pdf"),
    path("summary.pdf", faculty.summary_pdf, name="summary_pdf"),
]

staff_patterns = [
    path("", staff.dashboard, name="dashboard"),
    path("search/", staff.quick_search, name="search"),

    path("students/", people.students, name="students"),
    path("students/add/", people.student_form, name="student_add"),
    path("students/<int:pk>/", people.student_detail, name="student"),
    path("students/<int:pk>/edit/", people.student_form, name="student_edit"),
    path("students/<int:pk>/enroll/", people.student_enroll, name="student_enroll"),
    path("students/<int:pk>/enrollments/<int:enrollment_id>/remove/", people.student_unenroll,
         name="student_unenroll"),

    path("faculty/", people.faculty_list, name="faculty"),
    path("faculty/add/", people.faculty_form, name="faculty_add"),
    path("faculty/<int:pk>/", staff.faculty_results, name="faculty_results"),
    path("faculty/<int:pk>/edit/", people.faculty_form, name="faculty_edit"),
    path("faculty/<int:pk>/summary.pdf", staff.faculty_pdf, name="faculty_pdf"),

    path("accounts/", people.staff_list, name="accounts"),
    path("accounts/add/", people.staff_form, name="account_add"),
    path("accounts/<int:pk>/edit/", people.staff_form, name="account_edit"),

    path("students/<int:pk>/password/", people.set_password, {"kind": "students"}, name="student_password"),
    path("students/<int:pk>/delete/", people.person_delete, {"kind": "students"}, name="student_delete"),
    path("faculty/<int:pk>/password/", people.set_password, {"kind": "faculty"}, name="faculty_password"),
    path("faculty/<int:pk>/delete/", people.person_delete, {"kind": "faculty"}, name="faculty_delete"),
    path("accounts/<int:pk>/password/", people.set_password, {"kind": "accounts"}, name="account_password"),

    path("classes/", academics.classes, name="classes"),
    path("classes/add/", academics.class_form, name="class_add"),
    path("classes/<int:pk>/", academics.class_detail, name="class"),
    path("classes/<int:pk>/edit/", academics.class_form, name="class_edit"),
    path("classes/<int:pk>/delete/", academics.class_delete, name="class_delete"),
    path("classes/<int:pk>/enroll-section/", academics.class_enroll_section, name="class_enroll_section"),
    path("classes/<int:pk>/enrollments/<int:enrollment_id>/remove/", academics.class_unenroll,
         name="class_unenroll"),
    path("classes/<int:pk>/results/", staff.class_results, name="class_results"),
    path("classes/<int:pk>/report.pdf", staff.class_pdf, name="class_pdf"),

    path("questionnaire/", academics.questionnaire, name="questionnaire"),
    path("questionnaire/copy/", academics.questionnaire_copy, name="questionnaire_copy"),
    re_path(r"^questionnaire/(?P<kind>inventory|appraisal)/(?P<semester_id>\d+)/add/$", academics.statement_form,
            name="statement_add"),
    re_path(r"^questionnaire/(?P<kind>inventory|appraisal)/(?P<semester_id>\d+)/(?P<pk>\d+)/edit/$",
            academics.statement_form, name="statement_edit"),
    re_path(r"^questionnaire/(?P<kind>inventory|appraisal)/(?P<pk>\d+)/delete/$", academics.statement_delete,
            name="statement_delete"),

    path("results/", staff.results, name="results"),
    path("settings/", staff.settings_view, name="settings"),

    path("records/<slug:kind>/", records.record_list, name="records"),
    path("records/<slug:kind>/add/", records.record_form, name="record_add"),
    path("records/<slug:kind>/<int:pk>/edit/", records.record_form, name="record_edit"),
    path("records/<slug:kind>/<int:pk>/delete/", records.record_delete, name="record_delete"),
]

urlpatterns = [
    path("", auth.index, name="index"),
    path("auth/login/", auth.login_view, name="login"),
    path("auth/logout/", auth.logout_view, name="logout"),
    path("register/", auth.student_register, name="student_register"),
    path("student/", include((student_patterns, "student"))),
    path("faculty/", include((faculty_patterns, "faculty"))),
    path("staff/", include((staff_patterns, "staff"))),
]
