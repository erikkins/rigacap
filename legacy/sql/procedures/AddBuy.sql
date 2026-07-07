-- SqlProcedure: [dbo].[AddBuy]

set nocount on

declare @ticker varchar(5), @audit varchar(1000)
declare @now datetime
select @now = getdate()
select @ticker = ticker
from stock
where stockID = @stockID

if not exists (select * from stockbuy where stockID = @StockID and AtWhen = @AtWhenBuy)
		begin
			if exists (select * from stockbuy where stockID = @stockID and status=0)
				begin
					--we already have an open hold on this stock...reiterate									
					select @audit = @ticker + ' is already in an open transaction.  Reiterate'
					exec saveAudit @now,  @audit, @stockID, 'REITERATE','I'
				end
			else
				begin
				--Channel A		
				exec saveAudit @AtWhenBuy, @buycomment, @stockID, 'BUY', 'I'

				insert into StockBuy (stockID, WatchID, AtWhen, Comment, Shares, BuyIDLink, Channel, DWAPDate)
					values(@stockID, @watchIDBuy, @AtWhenBuy, @BuyComment, @Shares, @BuyIDLink, 'A', @DWAPDate)
				--Channel B
				insert into StockBuy (stockID, WatchID, AtWhen, Comment, Shares, BuyIDLink, Channel, DWAPDate)
					values(@stockID, @watchIDBuy, @AtWhenBuy, @BuyComment, @Shares, @BuyIDLink, 'B', @DWAPDate)
				--Channel C
				insert into StockBuy (stockID, WatchID, AtWhen, Comment, Shares, BuyIDLink, Channel, DWAPDate)
					values(@stockID, @watchIDBuy, @AtWhenBuy, @BuyComment, @Shares, @BuyIDLink, 'C', @DWAPDate)
				end
		end
else
		begin			
			select @audit = @ticker + ' has already been bought on ' + Convert(varchar,@AtWhenBuy,101) + '.  Reiterate'
			exec saveAudit @now,  @audit, @stockID, 'REITERATE','I'
		end
set nocount off
