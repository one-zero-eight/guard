from beanie import PydanticObjectId


class GoogleLinkException(Exception):
    pass


class UserAlreadyJoinedExceptionWithAnotherGmail(GoogleLinkException):
    def __init__(self, user_id: PydanticObjectId):
        self.user_id = user_id
        super().__init__(f"User {user_id} already joined the document")


class UserBannedException(GoogleLinkException):
    def __init__(self, user_id: PydanticObjectId):
        self.user_id = user_id
        super().__init__(f"User {user_id} is banned from the document")
