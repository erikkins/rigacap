-- SqlProcedure: [dbo].[getMemberByGuid]

set nocount on
	select * from Member where memberGuid = @MemberGUID

set nocount off
