-- SqlProcedure: [dbo].[clearCache]
-- header:
-- CREATE proc [dbo].[clearCache]

CREATE proc [dbo].[clearCache]
as
set nocount on

declare @today datetime
select @today = convert(char(4),datepart(year, getdate())) + '-' + right('00' + convert(varchar(2),datepart(month, getdate())),2) + '-'+ right('00' + convert(varchar(2), datepart(day, getdate())),2)

delete from DataCache
where CacheDate < @today

set nocount off
