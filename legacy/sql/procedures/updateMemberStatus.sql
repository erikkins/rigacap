-- SqlProcedure: [dbo].[updateMemberStatus]

set nocount on
	update member
	set status = @Status
	where memberID=@MemberID
set nocount off
