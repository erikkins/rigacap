-- SqlProcedure: [dbo].[AddBuyChannel]

set nocount on

declare @ticker varchar(5), @audit varchar(1000)
declare @now datetime
select @now = getdate()
select @ticker = ticker
from stock
where stockID = @stockID

if not exists (select * from stockbuy where stockID = @StockID and AtWhen = @AtWhenBuy and Channel=@Channel)
		begin
			if exists (select * from stockbuy where stockID = @stockID and status=0 and Channel=@Channel)
				begin
					--we already have an open hold on this stock...reiterate									
					select @audit = @ticker + ' is already in an open transaction.  Reiterate'
					return 0
					--exec saveAudit @now,  @audit, @stockID, 'REITERATE','I'
				end						

				if @IsRetro=1
					begin
					--final check...kludge for buying the day after another buy...don't buy again...regardless of status
					/*
					if exists (select * from stockbuy where stockID=@stockID and Channel=@Channel and DWAPDate=@DWAPDate)
						begin
							return 0
						end
					*/
					--now check if any other transactions have occurred where this dwap date is within the buy and sell date
					--find the first sell after this buydate and go backwards to see if there's a buy prior to this buydate...if so, don't buy
					declare @nextsell datetime
					select @nextsell = min(ss.atwhen) from stocksell ss inner join stockbuy sb on sb.buyID=ss.buyID where channel=@channel and stockID=@stockID and ss.atwhen >= @AtWhenBuy
					if @nextsell is not null
						begin
							declare @lastBuy datetime
							select @lastBuy = atwhen
							from StockBuy
							where BuyID = (select top 1 sb.buyID from stockbuy sb inner join stocksell ss on ss.buyID=sb.buyID where stockID=@stockID and channel=@Channel and ss.atwhen=@nextsell)

							if @lastBuy < @AtWhenBuy
								begin
									--Print 'Buying during buy'
									return 0
								end
						end
				/*
					if exists (select * from stockbuy sb left join stocksell ss on ss.buyID=sb.buyID where sb.stockID = @stockID and sb.Channel = @Channel and @atWhenBuy between sb.atwhen and case when ss.atwhen is null then dateadd(day,1,@atWhenBuy) else ss.atwhen end)
						begin
							--we already have a transaction in this date period
							Print 'Open Buy Still Open'
							return 0
						end
				*/
					end
				
				exec saveAudit @AtWhenBuy, @buycomment, @stockID, 'BUY', 'I'

				insert into StockBuy (stockID, WatchID, AtWhen, Comment, Shares, BuyIDLink, Channel, DWAPDate)
					values(@stockID, @watchIDBuy, @AtWhenBuy, @BuyComment, @Shares, @BuyIDLink, @Channel, @DWAPDate)				
			
				return @@IDENTITY
		end
else
		begin			
			--Print 'Already bought on that date'
			return 0		
			select @audit = @ticker + ' has already been bought on ' + Convert(varchar,@AtWhenBuy,101) + '.  Reiterate'
			--exec saveAudit @now,  @audit, @stockID, 'REITERATE','I'
		end
set nocount off
