"""ScoreMax V6.1 deterministic Teacher Discovery & Academic Messages smoke suite."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs


class Form(dict):
    def getlist(self,key):
        value=self.get(key,[])
        return value if isinstance(value,list) else [value]


def main():
    flask,request=install_framework_stubs()
    temp=Path(tempfile.mkdtemp(prefix='scoremax_v61_smoke_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db')
    os.environ['SCOREMAX_ENV']='local'
    import app
    from academic_messaging_engine import detect_message_policy, validate_teacher_listing, profile_completeness

    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)

    app.init(); app.init()
    c=app.db()
    ok('V6.1 schema and feature controls are idempotent',c.execute("SELECT COUNT(*) n FROM community_feature_controls").fetchone()['n']==4)
    ok('Teacher Discovery and Academic Messages are pilot-only by default',
       c.execute("SELECT state FROM community_feature_controls WHERE feature_code='teacher_discovery'").fetchone()['state']=='PILOT' and
       c.execute("SELECT state FROM community_feature_controls WHERE feature_code='academic_messages'").fetchone()['state']=='PILOT')
    ok('unrestricted student direct messaging is structurally hidden',c.execute("SELECT state FROM community_feature_controls WHERE feature_code='student_direct_messages'").fetchone()['state']=='HIDDEN')

    teacher_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,teacher_marketplace_pilot_enabled,academic_messages_pilot_enabled)
      VALUES('TCH-V61-1','teacher','Dr Sana Malik','1988-04-05','sana@test','sana','x','active',1,1)""").lastrowid
    student_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,teacher_marketplace_pilot_enabled,academic_messages_pilot_enabled)
      VALUES('STU-V61-1','student','Adult Student','2002-02-03','adult@test','adult','x','active',1,1)""").lastrowid
    minor_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,teacher_marketplace_pilot_enabled,academic_messages_pilot_enabled)
      VALUES('STU-V61-2','student','Minor Student','2011-02-03','minor@test','minor','x','active',1,1)""").lastrowid
    no_dob_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,teacher_marketplace_pilot_enabled,academic_messages_pilot_enabled)
      VALUES('STU-V61-3','student','DOB Missing','nodob@test','nodob','x','active',1,1)""").lastrowid
    parent_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status)
      VALUES('PAR-V61-1','parent','Parent User','1980-01-01','parent@test','parent','x','active')""").lastrowid
    other_student_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,teacher_marketplace_pilot_enabled,academic_messages_pilot_enabled)
      VALUES('STU-V61-4','student','Second Student','2001-01-01','second@test','second','x','active',1,1)""").lastrowid
    c.execute("INSERT INTO parent_student_links(parent_user_id,student_user_id,relationship,status) VALUES(?,?, 'Parent','active')",(parent_id,minor_id))
    c.commit()
    ok('pilot access is separate for discovery and messaging',app.community_feature_available(c,student_id,'teacher_discovery') and app.community_feature_available(c,student_id,'academic_messages'))
    ok('missing date of birth blocks teacher messaging',not app.student_messaging_safety_ready(c,no_dob_id)['allowed'])
    ok('known minor requires explicit guardian consent',not app.student_messaging_safety_ready(c,minor_id)['allowed'])
    ok('adult student does not require guardian consent',app.student_messaging_safety_ready(c,student_id)['allowed'])
    c.close()

    # Explicit, versioned community and teacher-conduct agreements.
    for uid,role,codes in [
        (teacher_id,'teacher',['ACADEMIC_MESSAGES_USER','TEACHER_MARKETPLACE_CONDUCT']),
        (student_id,'student',['ACADEMIC_MESSAGES_USER']),
        (minor_id,'student',['ACADEMIC_MESSAGES_USER'])]:
        flask.session.clear(); flask.session.update({'user_id':uid,'role':role,'full_name':'Agreement User'})
        for code in codes:
            request.form=Form({'decision':'ACCEPTED'}); app.community_agreement_accept(code)
    c=app.db()
    ok('messaging and teacher conduct require explicit versioned agreements',c.execute("SELECT COUNT(*) n FROM community_user_agreements WHERE status='ACCEPTED'").fetchone()['n']==4 and app.community_agreements_ready(c,teacher_id,'teacher') and app.community_agreements_ready(c,student_id,'student'))
    c.close()

    normal=detect_message_policy('Please help me explain enzyme denaturation.','student','TEXT')
    ok('ordinary academic message is visible',normal['moderation_status']=='VISIBLE' and not normal['flags'])
    ok('phone numbers and WhatsApp references are held',detect_message_policy('WhatsApp me on 03001234567','student','TEXT')['moderation_status']=='HELD')
    ok('student cannot send a meeting link as a teacher-controlled message',detect_message_policy('https://meet.google.com/abc-defg-hij','student','MEETING_LINK')['moderation_status']=='HELD')
    ok('teacher may send an approved meeting-domain link',detect_message_policy('Join https://meet.google.com/abc-defg-hij','teacher','MEETING_LINK')['moderation_status']=='VISIBLE')
    ok('unapproved external links are held during the controlled pilot',detect_message_policy('Open https://unknown.example/file','teacher','TEXT')['moderation_status']=='HELD')
    ok('group listing validation requires realistic capacity',not validate_teacher_listing({'service_type':'GROUP','title':'Group','subject':'Biology','capacity':1,'price_minor':0,'platforms':'Meet'})['valid'])

    # Teacher profile creation and governance.
    flask.session.clear(); flask.session.update({'user_id':teacher_id,'role':'teacher','full_name':'Dr Sana Malik'})
    request.form=Form({'headline':'FSc and MDCAT Biology teacher','bio':'Experienced Biology teacher focused on clear explanations, exam technique and safe academic support.',
      'subjects':'Biology,Chemistry','frameworks':'FSc,MDCAT','qualifications_text':'MSc Biology; BEd','experience_years':'9','languages':'English,Urdu',
      'delivery_modes':'Online,Local','platforms':'Google Meet,Zoom','location_text':'Lahore','price_from':'1500','availability_text':'Evenings and weekends',
      'response_expectation_hours':'12','office_hours':'Monday to Saturday, 5pm–9pm','allow_one_to_one':'on','allow_groups':'on','submit_for_review':'1'})
    app.teacher_marketplace_profile_save()
    c=app.db(); profile=c.execute("SELECT * FROM teacher_profiles WHERE teacher_id=?",(teacher_id,)).fetchone()
    ok('teacher creates a moderated professional profile',profile and profile['profile_status']=='PENDING_REVIEW' and profile_completeness(dict(profile))>=60)
    c.close()

    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.form=Form({'decision':'PUBLISHED','note':'Attempt before identity verification'})
    app.admin_teacher_profile_review(teacher_id)
    c=app.db(); ok('profile cannot publish before identity verification',c.execute("SELECT profile_status FROM teacher_profiles WHERE teacher_id=?",(teacher_id,)).fetchone()['profile_status']=='PENDING_REVIEW'); c.close()
    request.form=Form({'verification_type':'identity','status':'VERIFIED','evidence_note':'Identity document checked in pilot.'})
    app.admin_teacher_verification(teacher_id)
    request.form=Form({'verification_type':'qualification','status':'VERIFIED','evidence_note':'Qualification evidence checked.'})
    app.admin_teacher_verification(teacher_id)
    request.form=Form({'decision':'PUBLISHED','note':'Profile complete and identity verified.'})
    app.admin_teacher_profile_review(teacher_id)
    c=app.db(); profile=c.execute("SELECT * FROM teacher_profiles WHERE teacher_id=?",(teacher_id,)).fetchone()
    ok('admin can publish a complete identity-verified profile',profile['profile_status']=='PUBLISHED' and profile['identity_verification_status']=='VERIFIED')
    ok('verification events are independently audited',c.execute("SELECT COUNT(*) n FROM teacher_verification_events WHERE teacher_id=?",(teacher_id,)).fetchone()['n']==2)
    c.close()

    # One-to-one and group listings.
    flask.session.clear(); flask.session.update({'user_id':teacher_id,'role':'teacher','full_name':'Dr Sana Malik'})
    request.form=Form({'service_type':'ONE_TO_ONE','title':'FSc Biology 1-to-1 support','description':'Targeted support based on verified ScoreMax weaknesses.',
      'subject':'Biology','framework':'FSc','chapter_scope':'Part I chapters','delivery_mode':'ONLINE','price':'1800','capacity':'1','platforms':'Google Meet,Zoom','availability_text':'Evenings','submit_for_review':'1'})
    app.teacher_listing_create()
    request.form=Form({'service_type':'GROUP','title':'MDCAT Biology revision group','description':'Teacher-led weekly group revision and question discussion.',
      'subject':'Biology','framework':'MDCAT','chapter_scope':'Full syllabus','delivery_mode':'ONLINE','price':'3000','capacity':'25','platforms':'Google Meet','availability_text':'Saturday','submit_for_review':'1'})
    app.teacher_listing_create()
    c=app.db(); listings=c.execute("SELECT * FROM teacher_service_listings WHERE teacher_id=? ORDER BY id",(teacher_id,)).fetchall()
    one_id=listings[0]['id']; group_listing_id=listings[1]['id']
    ok('teacher can advertise separate one-to-one and group services',len(listings)==2 and {x['service_type'] for x in listings}=={'ONE_TO_ONE','GROUP'})
    c.close()
    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    for listing_id in (one_id,group_listing_id):
        request.form=Form({'decision':'PUBLISHED','note':'Moderated pilot listing.'}); app.admin_teacher_listing_review(listing_id)
    c=app.db(); ok('only admin-published listings become discoverable',c.execute("SELECT COUNT(*) n FROM teacher_service_listings WHERE listing_status='PUBLISHED'").fetchone()['n']==2); c.close()

    # Parent approves minor messaging.
    flask.session.clear(); flask.session.update({'user_id':parent_id,'role':'parent','full_name':'Parent User'})
    request.form=Form({'decision':'APPROVED'}); app.parent_academic_messaging_decision(minor_id)
    c=app.db(); ok('linked parent gives separately versioned under-18 messaging consent',app.student_messaging_safety_ready(c,minor_id)['allowed'] and c.execute("SELECT consent_text_version FROM academic_guardian_consents WHERE student_id=?",(minor_id,)).fetchone()['consent_text_version']=='V6.1-GUARDIAN-1'); c.close()

    # Enquiry safety and accepted relationship.
    flask.session.clear(); flask.session.update({'user_id':student_id,'role':'student','full_name':'Adult Student'})
    request.form=Form({'listing_id':str(one_id),'support_need':'I need help explaining enzyme action.','preferred_mode':'Online','initial_message':'WhatsApp me on 03001234567'})
    app.teacher_enquiry_create(teacher_id)
    c=app.db(); ok('structured enquiry rejects personal contact sharing',c.execute("SELECT COUNT(*) n FROM teacher_enquiries WHERE student_id=?",(student_id,)).fetchone()['n']==0); c.close()
    request.form=Form({'listing_id':str(one_id),'support_need':'I need help explaining enzyme action and interpreting my recovery-test feedback.','preferred_mode':'Online','initial_message':'Could you help me with the causal explanation?'})
    app.teacher_enquiry_create(teacher_id)
    c=app.db(); enquiry=c.execute("SELECT * FROM teacher_enquiries WHERE student_id=?",(student_id,)).fetchone()
    ok('student creates a number-private structured enquiry',enquiry and enquiry['status']=='PENDING' and enquiry['guardian_consent_status']=='NOT_REQUIRED')
    c.close()
    flask.session.clear(); flask.session.update({'user_id':teacher_id,'role':'teacher','full_name':'Dr Sana Malik'})
    request.form=Form({'decision':'ACCEPTED'}); app.teacher_enquiry_respond(enquiry['id'])
    c=app.db(); conv=c.execute("SELECT * FROM academic_conversations WHERE enquiry_id=?",(enquiry['id'],)).fetchone()
    ok('accepted enquiry creates a governed one-to-one academic conversation',conv and conv['conversation_type']=='ONE_TO_ONE' and c.execute("SELECT COUNT(*) n FROM academic_conversation_members WHERE conversation_id=? AND status='ACTIVE'",(conv['id'],)).fetchone()['n']==2)
    ok('teacher cannot initiate an unsolicited random conversation through the product flow',c.execute("SELECT COUNT(*) n FROM academic_conversations WHERE enquiry_id IS NULL AND conversation_type='ONE_TO_ONE'").fetchone()['n']==0)
    engagement=c.execute("SELECT * FROM teacher_engagements WHERE conversation_id=?",(conv['id'],)).fetchone(); c.close()

    # Guardian consent is re-checked when a teacher accepts, not only when the enquiry is created.
    flask.session.clear(); flask.session.update({'user_id':minor_id,'role':'student','full_name':'Minor Student'})
    request.form=Form({'listing_id':str(one_id),'support_need':'I need help with FSc Biology terminology.','preferred_mode':'Online','initial_message':'Please tell me whether you cover this chapter.'})
    app.teacher_enquiry_create(teacher_id)
    c=app.db(); minor_enquiry=c.execute("SELECT * FROM teacher_enquiries WHERE student_id=? AND status='PENDING'",(minor_id,)).fetchone(); c.close()
    flask.session.clear(); flask.session.update({'user_id':parent_id,'role':'parent','full_name':'Parent User'})
    request.form=Form({'decision':'REVOKED'}); app.parent_academic_messaging_decision(minor_id)
    flask.session.clear(); flask.session.update({'user_id':teacher_id,'role':'teacher','full_name':'Dr Sana Malik'})
    request.form=Form({'decision':'ACCEPTED'}); app.teacher_enquiry_respond(minor_enquiry['id'])
    c=app.db(); ok('teacher acceptance re-checks current guardian consent',c.execute("SELECT status FROM teacher_enquiries WHERE id=?",(minor_enquiry['id'],)).fetchone()['status']=='CANCELLED_SAFETY' and c.execute("SELECT COUNT(*) n FROM academic_conversations WHERE enquiry_id=?",(minor_enquiry['id'],)).fetchone()['n']==0); c.close()
    flask.session.clear(); flask.session.update({'user_id':parent_id,'role':'parent','full_name':'Parent User'})
    request.form=Form({'decision':'APPROVED'}); app.parent_academic_messaging_decision(minor_id)

    # Message policy at persistence layer.
    flask.session.clear(); flask.session.update({'user_id':student_id,'role':'student','full_name':'Adult Student'})
    request.form=Form({'message_type':'TEXT','body':'Please explain why high temperature changes the active site.'}); app.academic_message_send(conv['id'])
    request.form=Form({'message_type':'TEXT','body':'My number is 03001234567'}); app.academic_message_send(conv['id'])
    request.form=Form({'message_type':'MEETING_LINK','body':'https://meet.google.com/student-link'}); app.academic_message_send(conv['id'])
    flask.session.clear(); flask.session.update({'user_id':teacher_id,'role':'teacher','full_name':'Dr Sana Malik'})
    request.form=Form({'message_type':'MEETING_LINK','body':'Our lesson link is https://meet.google.com/abc-defg-hij'}); app.academic_message_send(conv['id'])
    c=app.db()
    ok('normal teacher-student academic message is visible',c.execute("SELECT COUNT(*) n FROM academic_messages WHERE conversation_id=? AND moderation_status='VISIBLE' AND message_type='TEXT'",(conv['id'],)).fetchone()['n']>=1)
    ok('personal-number and student-meeting messages are held with audit reports',c.execute("SELECT COUNT(*) n FROM academic_messages WHERE conversation_id=? AND moderation_status='HELD'",(conv['id'],)).fetchone()['n']==2 and c.execute("SELECT COUNT(*) n FROM academic_message_reports WHERE conversation_id=? AND status='OPEN'",(conv['id'],)).fetchone()['n']==2)
    ok('teacher-approved meeting link remains visible',c.execute("SELECT COUNT(*) n FROM academic_messages WHERE conversation_id=? AND message_type='MEETING_LINK' AND moderation_status='VISIBLE'",(conv['id'],)).fetchone()['n']==1)
    c.close()

    # Verified completion and review.
    request.form=Form({'session_date':'2026-07-30'}); app.academic_confirm_engagement(conv['id'])
    flask.session.clear(); flask.session.update({'user_id':student_id,'role':'student','full_name':'Adult Student'})
    request.form=Form({'session_date':'2026-07-30'}); app.academic_confirm_engagement(conv['id'])
    c=app.db(); engagement=c.execute("SELECT * FROM teacher_engagements WHERE id=?",(engagement['id'],)).fetchone()
    ok('teacher rating unlocks only after both sides confirm the interaction',engagement['status']=='VERIFIED_COMPLETED' and engagement['teacher_confirmed'] and engagement['student_confirmed'])
    c.close()
    request.form=Form({'engagement_id':str(engagement['id']),'rating':'5','review_text':'Clear explanations and professional communication.'}); app.teacher_review_create(teacher_id)
    c=app.db(); review=c.execute("SELECT * FROM teacher_reviews WHERE engagement_id=?",(engagement['id'],)).fetchone()
    ok('verified review is held for moderation before public display',review and review['moderation_status']=='PENDING'); c.close()
    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.form=Form({'decision':'PUBLISHED'}); app.admin_teacher_review_moderate(review['id'])
    c=app.db(); summary=app.teacher_rating_summary(c,teacher_id)
    ok('published rating is based on a verified completed interaction',summary['review_count']==1 and summary['average_rating']==5.0); c.close()

    # Teacher-led group channel.
    flask.session.clear(); flask.session.update({'user_id':teacher_id,'role':'teacher','full_name':'Dr Sana Malik'})
    request.form=Form({'listing_id':str(group_listing_id),'name':'MDCAT Biology Saturday Group','description':'Weekly teacher-led revision group.','posting_policy':'TEACHER_ONLY','max_members':'25'})
    app.teacher_group_create()
    c=app.db(); group=c.execute("SELECT * FROM academic_groups WHERE teacher_id=?",(teacher_id,)).fetchone(); c.close()
    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.form=Form({'decision':'PUBLISHED'}); app.admin_teacher_group_review(group['id'])
    flask.session.clear(); flask.session.update({'user_id':minor_id,'role':'student','full_name':'Minor Student'})
    request.form=Form({}); app.teacher_group_join(group['id'])
    c=app.db(); membership=c.execute("SELECT * FROM academic_group_members WHERE group_id=? AND user_id=?",(group['id'],minor_id)).fetchone()
    ok('guardian-approved minor may request a moderated teacher group',membership and membership['status']=='PENDING'); c.close()
    flask.session.clear(); flask.session.update({'user_id':teacher_id,'role':'teacher','full_name':'Dr Sana Malik'})
    request.form=Form({'decision':'APPROVED'}); app.teacher_group_member_decision(group['id'],minor_id)
    c=app.db(); group_conv=c.execute("SELECT * FROM academic_conversations WHERE group_id=?",(group['id'],)).fetchone()
    ok('teacher approval adds student to teacher-owned group conversation',c.execute("SELECT status FROM academic_group_members WHERE group_id=? AND user_id=?",(group['id'],minor_id)).fetchone()['status']=='ACTIVE' and c.execute("SELECT COUNT(*) n FROM academic_conversation_members WHERE conversation_id=? AND status='ACTIVE'",(group_conv['id'],)).fetchone()['n']==2); c.close()
    flask.session.clear(); flask.session.update({'user_id':minor_id,'role':'student','full_name':'Minor Student'})
    before=app.db(); before_count=before.execute("SELECT COUNT(*) n FROM academic_messages WHERE conversation_id=?",(group_conv['id'],)).fetchone()['n']; before.close()
    request.form=Form({'message_type':'TEXT','body':'Can I post in this announcement group?'}); app.academic_message_send(group_conv['id'])
    c=app.db(); ok('teacher-only group policy prevents student posting',c.execute("SELECT COUNT(*) n FROM academic_messages WHERE conversation_id=?",(group_conv['id'],)).fetchone()['n']==before_count); c.close()
    flask.session.clear(); flask.session.update({'user_id':teacher_id,'role':'teacher','full_name':'Dr Sana Malik'})
    request.form=Form({'message_type':'TEXT','body':'Saturday revision starts at 6pm. Use the approved meeting link in the next post.'}); app.academic_message_send(group_conv['id'])
    c=app.db(); ok('teacher can post a visible group announcement',c.execute("SELECT COUNT(*) n FROM academic_messages WHERE conversation_id=? AND sender_id=? AND moderation_status='VISIBLE'",(group_conv['id'],teacher_id)).fetchone()['n']>=1); c.close()

    # Guardian revocation suspends access.
    flask.session.clear(); flask.session.update({'user_id':parent_id,'role':'parent','full_name':'Parent User'})
    request.form=Form({'decision':'REVOKED'}); app.parent_academic_messaging_decision(minor_id)
    c=app.db();
    ok('guardian revocation suspends existing group access without deleting evidence',c.execute("SELECT status FROM academic_group_members WHERE group_id=? AND user_id=?",(group['id'],minor_id)).fetchone()['status']=='GUARDIAN_REVOKED' and c.execute("SELECT status FROM academic_conversation_members WHERE conversation_id=? AND user_id=?",(group_conv['id'],minor_id)).fetchone()['status']=='GUARDIAN_REVOKED')
    c.close()

    # Direct block and admin policy fence.
    flask.session.clear(); flask.session.update({'user_id':student_id,'role':'student','full_name':'Adult Student'})
    request.form=Form({'blocked_user_id':str(teacher_id),'reason':'No further contact'}); app.academic_message_block(conv['id'])
    c=app.db(); ok('student block locks the direct conversation',c.execute("SELECT status FROM academic_conversations WHERE id=?",(conv['id'],)).fetchone()['status']=='LOCKED' and c.execute("SELECT active FROM academic_user_blocks WHERE blocker_id=? AND blocked_id=?",(student_id,teacher_id)).fetchone()['active']==1); c.close()
    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.form=Form({'state':'LIVE'}); app.admin_community_feature_update('student_direct_messages')
    c=app.db(); ok('admin cannot accidentally enable unrestricted student direct messages',c.execute("SELECT state FROM community_feature_controls WHERE feature_code='student_direct_messages'").fetchone()['state']=='HIDDEN')
    route_paths=[args[0] for args,kwargs,fn in app.app.routes if args]
    ok('no student-to-student direct-message route exists',not any('/students/' in path and 'message' in path for path in route_paths))
    c.close()

    from jinja2 import Environment
    env=Environment(); errors=[]
    for path in (ROOT/'templates').glob('*.html'):
        try: env.parse(path.read_text())
        except Exception as exc: errors.append((path.name,str(exc)))
    ok('all V6.1 templates parse',not errors)
    print(f'\nScoreMax V6.1 smoke suite: {len(checks)} checks passed.')
    print('Temporary database:',os.environ['SCOREMAX_DB'])

if __name__=='__main__': main()
