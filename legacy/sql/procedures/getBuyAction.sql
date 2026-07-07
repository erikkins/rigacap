-- SqlProcedure: [dbo].[getBuyAction]

set nocount on

select a.actionID, a.[Action], case when ba.actionid is null then 'false' else 'true' end as Checked
from [Action] a 
left outer join BuyAction ba on a.ActionID = ba.ActionID and ba.buyID=@BuyID

set nocount off
