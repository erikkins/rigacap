-- SqlProcedure: [dbo].[watchBuyStandardDev]

--this is a buy watch, but we're not using the startdate ever...


declare @watchID int
declare @ticker varchar(5)

declare @now datetime
select @now = getdate()
declare @audit varchar(8000)
declare @nowstring varchar(20)
select @nowstring = convert(varchar, @now,101)
select @watchID = watchID 
from Watch 
where ProcName = 'watchBuyStandardDev'

exec addWatchHistory @watchID, @now

declare @buyID int

declare @buys table
(
stockID int,
atwhen datetime
)

declare @sid int, @curdate datetime
declare scur cursor for
	select stockID from stock where active=1
open scur
fetch next from scur into @sid
	while @@fetch_status=0
		begin	
			Insert into @buys
			exec stdDev20Percent @sid, @nowstring	
		fetch next from scur into @sid
		end
close scur
deallocate scur

declare @cnt int
select @cnt = count(*) from @buys
declare @buydate datetime

if @cnt > 0
	begin

	declare buycur cursor for
		select stockID, atwhen from @buys

		open buycur
		fetch next from buycur into @sid, @buydate
		while @@fetch_status=0
			BEGIN
				select @audit = @ticker + ' exceeded 2X StdDev on 3X Volume and > 1.5MM volume '
				exec saveAudit @now,  @audit, @sid, 'EXCEEDSTDDEV','I'

				declare @comment varchar(1000)
				select @comment =  'Price exceeded 2X StdDev on 3X Volume and > 1.5MM volume'											
				exec @buyID = addbuyChannel @sid, @watchID, @buydate,@comment, null, 100, @channel, null, 1	
			fetch next from buycur into @sid, @buydate
			END
		close buycur
		deallocate buycur
	end
