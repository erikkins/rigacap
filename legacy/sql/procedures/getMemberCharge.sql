-- SqlProcedure: [dbo].[getMemberCharge]

set nocount on

	select * from Member m
	inner join MemberCharge mc on mc.MemberID=m.MemberID
	where mc.MemberChargeID = @MemberChargeID

set nocount off
