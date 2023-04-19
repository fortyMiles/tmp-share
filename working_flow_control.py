"""
This defines the (user-status, message-status) : [system-work1, system-work2, ...]
"""
from flask import request, jsonify
from user_worlflow.user import User
from user_worlflow.message import Message
from user_worlflow.notification import Reject, Welcome, InvitationWorks, GenerationInvitation, WorkingGroupNotification
from user_worlflow.notification import Information
from db_controller.user_related import PERSON_INVITE, GROUP_OR_VENDOR_INVITE, SYS
from db_controller.user_related import FORMAL_PAID, TRY
from dataclasses import dataclass
from ai_chatbot.ding_bot_controller.personal_chatbot_for_dingtalk import personal_qa
from typing import Union
from ai_chatbot.utils.utils import get_text_response
from functools import partial
from ai_chatbot.ding_bot_controller.process_image import process_receive_money_qa
from ai_chatbot.single_tasks import get_all_users_name_and_phone


ANY = '__any__'


@dataclass
class States:
    user_type: str
    user_expired: Union[bool, str]
    message_type: str
    message_expired: Union[bool, str]
    message_from: str
    message_function: str

    def __str__(self):
        return f'{self.message_type}, {self.message_expired}, {self.message_from}, {self.message_function}, ' \
               f'{self.user_type}, {self.user_expired}'

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        equal = True

        attributes = ['user_type', 'user_expired', 'message_type', 'message_expired', 'message_from', 'message_function']

        for attribute in attributes:
            if self.__getattribute__(attribute) == ANY:
                continue
            elif self.__getattribute__(attribute) == other.__getattribute__(attribute):
                continue
            else:
                equal = False
                break

        return equal


@dataclass
class UserState:
    user_type: str
    user_expired: Union[bool, str]

    def __str__(self):
        return f'{self.user_type}, {self.user_expired}'

    def __hash__(self):
        return hash(str(self))


@dataclass
class MessageState:
    message_type: str
    message_expired: Union[bool, str]
    message_from: str
    message_function: str

    def __str__(self):
        return f'{self.message_type}, {self.message_expired}, {self.message_from}, {self.message_function}'

    def __hash__(self):
        return hash(str(self))


def merge_state(us: UserState, ms: MessageState):
    return States(
        user_type=us.user_type,
        user_expired=us.user_expired,
        message_type=ms.message_type,
        message_from=ms.message_from,
        message_function=ms.message_function,
        message_expired=ms.message_expired
    )


TEXT, PICTURE, RICH_TEXT, OTHER = 'text', 'picture', 'richText', 'OTHER'


def get_http_request_info():
    sender_id = request.get_json()['senderStaffId']
    dialogue_type = request.get_json()['msgtype']
    if dialogue_type == TEXT:
        content = request.get_json()['text']['content'].strip()
    else:
        content = ''

    return sender_id, dialogue_type, content


def http_person_chat_with_verification(bot):

    sender_id, dialogue_type, content = get_http_request_info()

    return person_chat_handler(sender_id, dialogue_type, content, bot)


def person_chat_handler(sender_id, dialogue_type, content, bot, for_local_test=False):

    reject_helper = Reject(receiver=sender_id, personal_bot=bot)
    message_obj = Message(content=content)
    user = User(user_id=sender_id, message_obj=message_obj, bind_bot=bot)

    if dialogue_type == TEXT:
        content = request.get_json()['text']['content'].strip()
        qa_work = partial(personal_qa, bot=bot, sender_id=sender_id, content=content, user_workflow=user)
    elif dialogue_type == PICTURE and sender_id == 'manager9359':
        image_url = request.get_json()['content']['downloadCode']
        qa_work = partial(process_receive_money_qa, bot=bot, sender_id=sender_id, download_code=image_url)
    else:
        reject_helper.unsupported_msg_type()

    welcome_helper = Welcome(receiver=sender_id, personal_bot=bot)
    information_helper = Information(receiver=sender_id, user_workflow_obj=user, personal_bot=bot)

    if user.this_user_referee_type == PERSON_INVITE:
        invitor = user.this_user_referee
    else:
        invitor = None

    invitation_works_helper = InvitationWorks(receiver=invitor, code=user.verification_code, personal_bot=bot)
    generation_code_helper = GenerationInvitation(receiver=sender_id, personal_bot=bot)
    group_working_helper = WorkingGroupNotification(user=user, content=content)

    S_1 = UserState(user_type=User.INACTIVATE_OR_NEW, user_expired=ANY)
    S_2 = UserState(user_type=User.TRY, user_expired=True)
    S_3 = UserState(user_type=User.TRY, user_expired=False)
    S_4 = UserState(User.PAID_OR_EXTEND, user_expired=True)
    S_5 = UserState(User.PAID_OR_EXTEND, user_expired=False)

    M_1 = MessageState(Message.MESSAGE, message_expired=ANY, message_from=ANY, message_function=ANY)
    M_2 = MessageState(Message.ASK_ACTIVATION, message_expired=ANY, message_from=ANY, message_function=ANY)
    M_3 = MessageState(Message.VERIFICATION, message_expired=False, message_from=ANY,message_function=TRY)
    # M_4 = MessageState(Message.VERIFICATION, message_expired=False, message_from=PERSON_INVITE, message_function=TRY)
    M_5 = MessageState(Message.VERIFICATION, message_expired=False, message_from=SYS, message_function=FORMAL_PAID)
    # M_6 = MessageState(Message.VERIFICATION, message_expired=False, message_from=SYS, message_function=TRY)
    M_7 = MessageState(Message.VERIFICATION, message_expired=True, message_from=GROUP_OR_VENDOR_INVITE, message_function=ANY)
    M_8 = MessageState(Message.VERIFICATION, message_expired=True, message_from=PERSON_INVITE, message_function=ANY)
    M_9 = MessageState(Message.VERIFICATION, message_expired=True, message_from=SYS, message_function=FORMAL_PAID)
    M_10 = MessageState(Message.VERIFICATION, message_expired=True, message_from=SYS, message_function=TRY)

    # special cmd
    M_11 = MessageState(Message.QUERY_TIME, message_expired=ANY, message_from=ANY, message_function=ANY)
    M_12 = MessageState(Message.CLEAR_MEMORY, message_expired=ANY, message_from=ANY, message_function=ANY)

    state_work_flow_define = {
        # (user-state, message-state): ([responses, commit_change, working_notification])
        (S_1, M_1): [
            reject_helper.need_activate_p,
            user.save_a_new_inactivate_person,
            group_working_helper.invalid_verification_code
        ],

        (S_2, M_1): [
            reject_helper.try_expired_p,
            None,
            group_working_helper.expired_trying_user
        ],

        (S_3, M_1): [
            qa_work,
            None,
            None,
        ],

        (S_4, M_1): [
            reject_helper.formal_use_expired_p,
            None,
            group_working_helper.expired_paid_user,
        ],

        (S_5, M_1): [
            qa_work,
            None,
            None,
        ],

        (S_1, M_2): [
            generation_code_helper.generate,
            user.save_a_new_inactivate_person,
            group_working_helper.user_are_applying_invitation_code,
        ],

        (S_2, M_2): [
            generation_code_helper.generate,
            None,
            group_working_helper.user_are_applying_invitation_code
        ],

        (S_3, M_2): [
            generation_code_helper.generate,
            None,
            group_working_helper.user_are_applying_invitation_code
        ],

        (S_4, M_2): [
            generation_code_helper.generate,
            None,
            group_working_helper.user_are_applying_invitation_code
        ],

        (S_5, M_2): [
            generation_code_helper.generate,
            None,
            group_working_helper.user_are_applying_invitation_code
        ],

        (S_1, M_3): [
            welcome_helper.new_trying,
            [user.extend_trying_user, message_obj.update_verification_status],
            [invitation_works_helper.trying_success, group_working_helper.user_activate_trying_code,]
        ],

        (S_2, M_3): [
            reject_helper.already_tried_p,
            None,
            group_working_helper.trying_people_use_trying_code_again,
        ],

        (S_3, M_3): [
            reject_helper.already_tried_p,
            None,
            group_working_helper.trying_people_use_trying_code_again
        ],

        (S_4, M_3): [
            reject_helper.already_tried_p,
            None,
            group_working_helper.formal_people_use_trying
        ],

        (S_5, M_3): [
            reject_helper.paid_user_using_trying,
            None,
            group_working_helper.formal_people_use_trying,
        ],

        (S_1, M_5): [
            welcome_helper.new_paid,
            [user.extend_paid_user, message_obj.update_verification_status],
            [invitation_works_helper.send, group_working_helper.user_activate_paid],
        ],

        (S_2, M_5): [
            welcome_helper.paid_after_try,
            [user.extend_paid_user, message_obj.update_verification_status],
            [invitation_works_helper.send, group_working_helper.user_activate_paid],
        ],

        (S_3, M_5): [
            welcome_helper.paid_after_try,
            [user.extend_paid_user, message_obj.update_verification_status],
            [invitation_works_helper.send, group_working_helper.user_activate_paid]
        ],

        (S_4, M_5): [
            welcome_helper.paid_after_paid,
            [user.extend_paid_user, message_obj.update_verification_status],
            [invitation_works_helper.send, group_working_helper.user_activate_paid]
        ],

        (S_5, M_5):  [
            welcome_helper.paid_after_paid,
            [user.extend_paid_user, message_obj.update_verification_status],
            [invitation_works_helper.send, group_working_helper.user_activate_paid]
        ],

        (S_1, M_7): [reject_helper.expired_invitation_code_p, user.save_a_new_inactivate_person, group_working_helper.expired_code_user],
        (S_2, M_7): [reject_helper.already_tried_p, None, group_working_helper.trying_people_use_trying_code_again],
        (S_3, M_7): [reject_helper.already_tried_p, None, group_working_helper.trying_people_use_trying_code_again],
        (S_4, M_7): [reject_helper.already_tried_p, None, group_working_helper.formal_people_use_trying],
        (S_5, M_7): [reject_helper.paid_user_using_trying, None, group_working_helper.formal_people_use_trying],

        (S_1, M_8): [reject_helper.expired_invitation_code_p, user.save_a_new_inactivate_person, group_working_helper.expired_code_user],
        (S_2, M_8): [reject_helper.already_tried_p, None, group_working_helper.trying_people_use_trying_code_again],
        (S_3, M_8): [reject_helper.already_tried_p, None, group_working_helper.trying_people_use_trying_code_again],
        (S_4, M_8): [reject_helper.already_tried_p, None, group_working_helper.formal_people_use_trying],
        (S_5, M_8): [reject_helper.paid_user_using_trying, None, group_working_helper.formal_people_use_trying],

        (S_1, M_9): [reject_helper.expired_year_code_p, user.save_a_new_inactivate_person, group_working_helper.expired_code_user],
        (S_2, M_9): [reject_helper.expired_year_code_p, None, group_working_helper.expired_code_user],
        (S_3, M_9): [reject_helper.expired_year_code_p, None, group_working_helper.expired_code_user],
        (S_4, M_9): [reject_helper.expired_year_code_p, None, group_working_helper.expired_code_user],
        (S_5, M_9): [reject_helper.expired_year_code_p, None, group_working_helper.expired_code_user],

        (S_1, M_10): [reject_helper.expired_sys_code_p, user.save_a_new_inactivate_person, group_working_helper.expired_code_user],
        (S_2, M_10): [reject_helper.already_tried_p, None, group_working_helper.expired_code_user],
        (S_3, M_10): [reject_helper.already_tried_p, None, group_working_helper.expired_code_user],
        (S_4, M_10): [reject_helper.already_tried_p, None, group_working_helper.expired_code_user],
        (S_5, M_10): [reject_helper.paid_user_using_trying, None, group_working_helper.expired_code_user],

        (ANY, M_11): [information_helper.send_query_time, None, group_working_helper.query_valid_time],
        (ANY, M_12): [information_helper.clear_memory, user.set_need_refresh_memory, None],
    }

    states_and_actions_mapping = {}

    for (us, ms), actions in state_work_flow_define.items():
        if us == ANY:
            us = [S_1, S_2, S_3, S_4, S_5]
        elif isinstance(us, tuple):
            us = list(us)
        else:
            us = [us]

        for _us in us:
            states_and_actions_mapping[merge_state(us=_us, ms=ms)] = actions

    # states_and_actions_mapping = {
    #     merge_state(us=us, ms=ms): actions for (us, ms), actions in state_work_flow_define.items()
    # }

    current_state = merge_state(UserState(*user.status), MessageState(*message_obj.status))

    find_actions = False
    send_message_func, update_data_func, callbacks = None, None, []

    for state, actions in states_and_actions_mapping.items():
        if state == current_state:
            find_actions = True
            print('current state: ', state)
            print('current actions: ', actions)
            send_message_func, update_data_func, callbacks = actions
            break

    if not find_actions:
        raise TypeError(
            f'find an error when process user: {user.status} with message: {content}, as '
            f'{message_obj.status}, '
            f'we cannot find the right process workflow'
        )

    # execute send message

    send_message_func()

    # execute user state update
    if update_data_func is None:
        update_data_func = [user.save_user_last_action]
    elif not isinstance(update_data_func, (list, tuple)):
        update_data_func = [update_data_func]

    for commit_func in update_data_func:
        commit_func()

    # call back notification
    if callbacks is None:
        callbacks = []
    elif not isinstance(callbacks, (list, tuple)):
        callbacks = [callbacks]

    for back_func in callbacks:
        back_func()

    if not for_local_test:
        return jsonify(get_text_response('', user_id=""))


s1 = States(user_type='a', user_expired=ANY, message_type='t', message_expired=False,
            message_from='a', message_function='f')

s2 = States(user_type='a', user_expired=False, message_type='t', message_expired=False,
            message_from='a', message_function='f')

s3 = States(user_type='a', user_expired=False, message_type='y', message_expired=False,
            message_from='a', message_function='f')

assert s1 == s2
assert s1 != s3


if __name__ == '__main__':
    from ai_chatbot.ding_bot_controller.bot_basic_config.ding_p2p_talk_bot import DING_PERSON_TALK_BOT_TEST, \
        DING_PERSON_TALK_BOT, refresh_token

    refresh_token()

    minquan = 'manager9359'

    for _ in range(5):
        person_chat_handler(sender_id=minquan, dialogue_type=TEXT, content='___tst___你好', bot=DING_PERSON_TALK_BOT_TEST, for_local_test=True)
        person_chat_handler(sender_id=minquan, dialogue_type=TEXT, content='___tst___我的男朋友看我不顺眼怎么办', bot=DING_PERSON_TALK_BOT_TEST, for_local_test=True)