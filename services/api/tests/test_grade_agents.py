from app.commands.audit_grade_agents import audit


def test_public_only_agents_expose_category_shortcut(tmp_path):
    report = audit(tmp_path)
    assert report['forms'] == 45
    assert report['agents']['junior']['answeredUsingVisibleCategory'] == 0
    assert report['agents']['junior']['middlePassRate'] == 0
    assert report['agents']['junior']['seniorPassRate'] == 0
    assert report['agents']['senior']['seniorMeanScore'] >= report['agents']['junior']['seniorMeanScore']
    assert report['semanticStatus'] == 'NOT_VALIDATED'
